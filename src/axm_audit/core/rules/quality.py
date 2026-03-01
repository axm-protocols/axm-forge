"""Quality rules — linting, formatting, and type checking via subprocess."""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from axm_audit.core.rules.base import PASS_THRESHOLD, ProjectRule, register_rule
from axm_audit.core.runner import run_in_project
from axm_audit.models.results import CheckResult, Severity

__all__ = ["DiffSizeRule", "FormattingRule", "LintingRule", "TypeCheckRule"]

logger = logging.getLogger(__name__)


def _get_audit_targets(project_path: Path) -> tuple[list[str], str]:
    """Build the list of directories to audit and a human-readable label.

    Returns:
        ``(targets, checked)`` — e.g. ``(["src", "tests"], "src/ tests/")``.
    """
    src_path = project_path / "src"
    tests_path = project_path / "tests"
    targets = [str(src_path)]
    if tests_path.exists():
        targets.append(str(tests_path))
    checked = "src/ tests/" if tests_path.exists() else "src/"
    return targets, checked


@dataclass
@register_rule("lint")
class LintingRule(ProjectRule):
    """Run ruff and score based on issue count.

    Scoring: 100 - (issue_count * 2), min 0.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "QUALITY_LINT"

    def check(self, project_path: Path) -> CheckResult:
        """Check project linting with ruff on src/ and tests/."""
        early = self.check_src(project_path)
        if early is not None:
            return early
        targets, checked = _get_audit_targets(project_path)

        result = run_in_project(
            ["ruff", "check", "--output-format=json", *targets],
            project_path,
            capture_output=True,
            text=True,
            check=False,
        )

        try:
            issues = json.loads(result.stdout) if result.stdout.strip() else []
        except json.JSONDecodeError:
            issues = []

        issue_count = len(issues)
        score = max(0, 100 - issue_count * 2)
        passed = score >= PASS_THRESHOLD

        # Store individual violations (capped at 20) for agent mode
        formatted_issues: list[dict[str, str | int]] = [
            {
                "file": i.get("filename", ""),
                "line": i.get("location", {}).get("row", 0),
                "code": i.get("code", ""),
                "message": i.get("message", ""),
            }
            for i in issues[:20]
        ]

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Lint score: {score}/100 ({issue_count} issues)",
            severity=Severity.WARNING if not passed else Severity.INFO,
            details={
                "issue_count": issue_count,
                "score": score,
                "checked": checked,
                "issues": formatted_issues,
            },
            fix_hint=f"Run: ruff check --fix {checked}" if issue_count > 0 else None,
        )


@dataclass
@register_rule("lint")
class FormattingRule(ProjectRule):
    """Run ``ruff format --check`` and score based on unformatted file count.

    Scoring: 100 - (unformatted_count * 5), min 0.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "QUALITY_FORMAT"

    def check(self, project_path: Path) -> CheckResult:
        """Check project formatting with ruff format --check."""
        early = self.check_src(project_path)
        if early is not None:
            return early

        targets, checked = _get_audit_targets(project_path)

        result = run_in_project(
            ["ruff", "format", "--check", *targets],
            project_path,
            capture_output=True,
            text=True,
            check=False,
        )

        unformatted_files = self._parse_unformatted_files(result)
        unformatted_count = len(unformatted_files)

        score = max(0, 100 - unformatted_count * 5)
        passed = score >= PASS_THRESHOLD

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Format score: {score}/100 ({unformatted_count} unformatted)",
            severity=Severity.WARNING if not passed else Severity.INFO,
            details={
                "unformatted_count": unformatted_count,
                "unformatted_files": unformatted_files[:20],
                "score": score,
                "checked": checked,
            },
            fix_hint=(f"Run: ruff format {checked}" if unformatted_count > 0 else None),
        )

    @staticmethod
    def _parse_unformatted_files(
        result: subprocess.CompletedProcess[str],
    ) -> list[str]:
        """Extract unformatted file paths from ruff format --check output."""
        if result.returncode == 0:
            return []
        return [
            line.strip()
            for line in result.stdout.strip().split("\n")
            if line.strip()
            and not line.startswith("error")
            and not line.startswith("warning")
        ]


@dataclass
@register_rule("type")
class TypeCheckRule(ProjectRule):
    """Run mypy and score based on error count.

    Scoring: 100 - (error_count * 5), min 0.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "QUALITY_TYPE"

    def check(self, project_path: Path) -> CheckResult:
        """Check project type hints with mypy on src/ and tests/."""
        early = self.check_src(project_path)
        if early is not None:
            return early

        targets, checked = _get_audit_targets(project_path)

        result = run_in_project(
            ["mypy", "--no-error-summary", "--output", "json", *targets],
            project_path,
            capture_output=True,
            text=True,
            check=False,
        )

        error_count, errors = self._parse_mypy_errors(result.stdout)

        score = max(0, 100 - error_count * 5)
        passed = score >= PASS_THRESHOLD

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Type score: {score}/100 ({error_count} errors)",
            severity=Severity.WARNING if not passed else Severity.INFO,
            details={
                "error_count": error_count,
                "score": score,
                "checked": checked,
                "errors": errors,
            },
            fix_hint=(
                "Add type hints to functions and fix type errors"
                if error_count > 0
                else None
            ),
        )

    @staticmethod
    def _parse_mypy_errors(
        stdout: str,
    ) -> tuple[int, list[dict[str, str | int]]]:
        """Parse mypy JSON output and extract errors."""
        error_count = 0
        errors: list[dict[str, str | int]] = []
        if not stdout.strip():
            return error_count, errors

        for line in stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("severity") != "error":
                continue
            error_count += 1
            errors.append(
                {
                    "file": entry.get("file", ""),
                    "line": entry.get("line", 0),
                    "message": entry.get("message", ""),
                    "code": entry.get("code", ""),
                }
            )
        return error_count, errors


# Regex for git diff --stat summary line:
# "N files changed, X insertions(+), Y deletions(-)"
_DIFF_STAT_RE = re.compile(
    r"(\d+)\s+files?\s+changed"
    r"(?:,\s*(\d+)\s+insertions?\(\+\))?"
    r"(?:,\s*(\d+)\s+deletions?\(-\))?",
)

# Thresholds for DiffSizeRule scoring
_DIFF_IDEAL = 200
_DIFF_MAX = 800


@dataclass
@register_rule("lint")
class DiffSizeRule(ProjectRule):
    """Warn when uncommitted changes are too large.

    Encourages smaller, focused commits/PRs.

    Scoring: 100 if < 200 lines changed, linear degrade to 0 at 800 lines.
    Gracefully skips if not in a git repository or git is not installed.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "QUALITY_DIFF_SIZE"

    def check(self, project_path: Path) -> CheckResult:
        """Check uncommitted diff size."""
        if shutil.which("git") is None:
            return self._skip("git not installed")

        if not self._is_git_repo(project_path):
            return self._skip("not a git repo")

        return self._measure_diff(project_path)

    # -- private helpers -------------------------------------------------------

    def _skip(self, reason: str) -> CheckResult:
        """Return graceful skip result."""
        return CheckResult(
            rule_id=self.rule_id,
            passed=True,
            message=f"{reason} — diff size check skipped",
            severity=Severity.INFO,
            details={"lines_changed": 0, "score": 100},
        )

    @staticmethod
    def _is_git_repo(project_path: Path) -> bool:
        """Check whether *project_path* is inside a git repository."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=str(project_path),
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        except OSError:
            return False

    def _measure_diff(self, project_path: Path) -> CheckResult:
        """Run ``git diff --stat HEAD`` and score the result."""
        try:
            result = subprocess.run(
                ["git", "diff", "--stat", "HEAD"],
                cwd=str(project_path),
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return self._skip("git command failed")

        stdout = result.stdout.strip()
        if not stdout:
            # No uncommitted changes
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message="No uncommitted changes",
                severity=Severity.INFO,
                details={"lines_changed": 0, "score": 100},
            )

        lines_changed = self._parse_stat(stdout)
        score = self._compute_score(lines_changed)
        passed = score >= PASS_THRESHOLD

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Diff size: {lines_changed} lines changed (score {score}/100)",
            severity=Severity.WARNING if not passed else Severity.INFO,
            details={"lines_changed": lines_changed, "score": score},
            fix_hint=(
                "Consider splitting into smaller commits (< 200 lines ideal)"
                if not passed
                else None
            ),
        )

    @staticmethod
    def _parse_stat(stdout: str) -> int:
        """Extract total lines changed from ``git diff --stat`` output."""
        last_line = stdout.strip().split("\n")[-1]
        match = _DIFF_STAT_RE.search(last_line)
        if not match:
            return 0
        insertions = int(match.group(2) or 0)
        deletions = int(match.group(3) or 0)
        return insertions + deletions

    @staticmethod
    def _compute_score(lines_changed: int) -> int:
        """Compute score from lines changed: 100→0 over [200, 800]."""
        if lines_changed <= _DIFF_IDEAL:
            return 100
        if lines_changed >= _DIFF_MAX:
            return 0
        return int(
            100 - (lines_changed - _DIFF_IDEAL) * 100 / (_DIFF_MAX - _DIFF_IDEAL)
        )
