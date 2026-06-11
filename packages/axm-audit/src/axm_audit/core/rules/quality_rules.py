"""Quality rules — linting, formatting, and type checking via subprocess."""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path

from axm_audit.core.rules.base import (
    LINT_PASS_THRESHOLD,
    PASS_THRESHOLD,
    ProjectRule,
    register_rule,
)
from axm_audit.core.runner import run_in_project
from axm_audit.models.results import CheckResult, Severity

__all__ = [
    "DiffSizeRule",
    "FormattingRule",
    "LintingRule",
    "TypeCheckRule",
    "detect_env_incompleteness",
]

logger = logging.getLogger(__name__)

# mypy error codes that signal the *audited environment* is incomplete
# (a missing dependency / missing type stubs), not a code defect.
_ENV_INCOMPLETE_CODES = frozenset({"import-untyped", "import-not-found"})
# mypy exit codes: 0 = clean, 1 = errors found, anything else = the check
# did not complete (blocking/usage/config/internal error). 124 = our own
# timeout sentinel from run_in_project.
_MYPY_DID_NOT_COMPLETE = frozenset({2, 124})
_QUOTED_NAME = re.compile(r'"([^"]+)"')


def detect_env_incompleteness(stdout: str, returncode: int) -> str | None:
    """Return an actionable diagnostic when the mypy run is unreliable.

    The type audit must never report a green score off the back of an
    *incomplete environment*. This classifier inspects mypy's JSON output
    and exit code for the signals that mean "the check did not actually
    type-check the code":

    * missing third-party stubs / unfollowed imports
      (``[import-untyped]``, ``Library stubs not installed for "..."``),
    * a module truly absent from the env (``[import-not-found]``),
    * a blocking/aborted mypy run (exit code 2, or our timeout sentinel),
      which emits non-JSON text that the JSON parser silently drops.

    Args:
        stdout: Raw mypy stdout (``--output json`` plus any plain-text
            blocking errors).
        returncode: mypy's process exit code.

    Returns:
        An actionable, single-line diagnostic naming the offending
        library/libraries and the remediation, or ``None`` when the run
        completed and exposes no env-incompleteness (a plain type error
        is a code problem, not an env problem).
    """
    libs: list[str] = []
    for line in stdout.strip().split("\n"):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        message = str(entry.get("message", ""))
        is_env_code = entry.get("code") in _ENV_INCOMPLETE_CODES
        is_stub_note = "Library stubs not installed" in message
        if is_env_code or is_stub_note:
            match = _QUOTED_NAME.search(message)
            if match:
                libs.append(match.group(1))

    if libs:
        unique = sorted(dict.fromkeys(libs))
        return (
            f"audit environment incomplete — missing type stubs or "
            f"unfollowed imports for: {', '.join(unique)}. The type result "
            f"is unreliable until the env is fixed (install the stubs / "
            f"run `uv sync`); this is an environment problem, not a code "
            f"problem."
        )

    if returncode in _MYPY_DID_NOT_COMPLETE:
        return (
            f"audit environment unreliable — mypy did not complete "
            f"(exit code {returncode}: blocking/config error or timeout). "
            f"The type result is unreliable until the env/config is fixed "
            f"(run `uv sync`); this is an environment problem, not a code "
            f"problem."
        )

    return None


def _short_path(filepath: str, project_path: Path) -> str:
    """Return *filepath* relative to *project_path*, or unchanged on failure."""
    try:
        return str(Path(filepath).relative_to(project_path))
    except ValueError:
        return filepath


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
            with_packages=["ruff"],
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
        passed = score >= LINT_PASS_THRESHOLD

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

        text_lines = [
            f"\u2022 {i['code']} {_short_path(str(i['file']), project_path)}"
            f":{i['line']} {i['message']}"
            for i in formatted_issues
        ]

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Lint score: {score}/100 ({issue_count} issues)",
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=int(score),
            details={
                "issue_count": issue_count,
                "checked": checked,
                "issues": formatted_issues,
            },
            text="\n".join(text_lines) if text_lines else None,
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
            with_packages=["ruff"],
            capture_output=True,
            text=True,
            check=False,
        )

        unformatted_files = self._parse_unformatted_files(result)
        unformatted_count = len(unformatted_files)

        score = max(0, 100 - unformatted_count * 5)
        passed = score >= PASS_THRESHOLD

        text_lines = unformatted_files[:20]

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Format score: {score}/100 ({unformatted_count} unformatted)",
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=int(score),
            details={
                "unformatted_count": unformatted_count,
                "unformatted_files": unformatted_files[:20],
                "checked": checked,
            },
            text="\n".join(text_lines) if text_lines else None,
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
    """Run mypy with zero-tolerance for errors.

    Scoring: 100 - (error_count * 5), min 0.
    Pass/fail: any error means failure (matches pre-commit mypy hook).
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

        error_count, errors = self.parse_mypy_errors(result.stdout)

        env_problem = detect_env_incompleteness(result.stdout, result.returncode)

        text_lines = [
            f"• [{e['code']}] {str(e['file']).removeprefix('src/')}"
            f":{e['line']}: {e['message']}"
            for e in errors
        ]

        if env_problem is not None:
            # Fail loud: an incomplete env must never yield a green score,
            # even when mypy emitted zero parseable JSON errors (exit 2).
            score = min(error_count and max(0, 100 - error_count * 5), 50)
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message=f"Type check BLOCKED: {env_problem}",
                severity=Severity.ERROR,
                score=int(score),
                details={
                    "error_count": error_count,
                    "checked": checked,
                    "errors": errors,
                    "env_incomplete": True,
                },
                text="\n".join(text_lines) if text_lines else None,
                fix_hint=env_problem,
            )

        score = max(0, 100 - error_count * 5)
        passed = error_count == 0

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Type score: {score}/100 ({error_count} errors)",
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=int(score),
            details={
                "error_count": error_count,
                "checked": checked,
                "errors": errors,
            },
            text="\n".join(text_lines) if text_lines else None,
            fix_hint=(
                "Add type hints to functions and fix type errors"
                if error_count > 0
                else None
            ),
        )

    @staticmethod
    def parse_mypy_errors(
        stdout: str,
    ) -> tuple[int, list[dict[str, str | int]]]:
        """Parse mypy JSON output and extract errors.

        Non-dict JSON lines (strings, arrays, ints, nulls) emitted by
        ``mypy --output json`` are silently skipped.
        """
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
            if not isinstance(entry, dict):
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
_DIFF_IDEAL = 400
_DIFF_MAX = 1200


def read_diff_config(project_path: Path) -> tuple[int, int]:
    """Read diff-size thresholds from ``[tool.axm-audit]`` in pyproject.toml.

    Returns:
        ``(ideal, max_lines)`` — falls back to module defaults on any error.
    """
    pyproject = project_path / "pyproject.toml"
    if not pyproject.exists():
        return _DIFF_IDEAL, _DIFF_MAX

    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return _DIFF_IDEAL, _DIFF_MAX

    section = data.get("tool", {}).get("axm-audit", {})

    raw_ideal = section.get("diff_size_ideal", _DIFF_IDEAL)
    raw_max = section.get("diff_size_max", _DIFF_MAX)

    try:
        ideal = int(raw_ideal)
    except (TypeError, ValueError):
        ideal = _DIFF_IDEAL

    try:
        max_lines = int(raw_max)
    except (TypeError, ValueError):
        max_lines = _DIFF_MAX

    if ideal < 0:
        ideal = _DIFF_IDEAL
    if max_lines < 0:
        max_lines = _DIFF_MAX

    return ideal, max_lines


@dataclass
@register_rule("lint")
class DiffSizeRule(ProjectRule):
    """Warn when uncommitted changes are too large.

    Encourages smaller, focused commits/PRs.

    Scoring: 100 if ≤ *ideal* lines changed, linear degrade to 0 at *max*
    lines.  Defaults: ideal=400, max=1200.  Overridable via
    ``[tool.axm-audit]`` in ``pyproject.toml``.

    Gracefully skips if not in a git repository or git is not installed.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "QUALITY_DIFF_SIZE"

    def check(self, project_path: Path) -> CheckResult:
        """Check uncommitted diff size."""
        project_path = Path(project_path)
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
            score=100,
            details={"lines_changed": 0},
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
        """Run ``git diff --stat HEAD`` and score the result.

        Counts uncommitted changed lines via ``git diff --stat``, computes a
        score against configurable *ideal* / *max* thresholds, and returns a
        :class:`CheckResult`.  When the check passes (score ≥ 90) or there are
        no changes, ``text`` is ``None`` so the result is omitted from
        agent-facing output.
        """
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
                score=100,
                details={"lines_changed": 0},
            )

        ideal, max_lines = read_diff_config(project_path)
        lines_changed = self._parse_stat(stdout)
        score = self.compute_score(lines_changed, ideal, max_lines)
        passed = score >= PASS_THRESHOLD

        text = (
            f"\u2022 {lines_changed} lines \u0394 (ideal < {ideal})"
            if not passed and lines_changed > 0
            else None
        )

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Diff size: {lines_changed} lines changed (score {score}/100)",
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=int(score),
            details={"lines_changed": lines_changed},
            text=text,
            fix_hint=(
                f"Consider splitting into smaller commits (< {ideal} lines ideal)"
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
    def compute_score(
        lines_changed: int,
        ideal: int = _DIFF_IDEAL,
        max_lines: int = _DIFF_MAX,
    ) -> int:
        """Compute score from lines changed: 100→0 over [ideal, max_lines]."""
        if lines_changed <= ideal:
            return 100
        if lines_changed >= max_lines:
            return 0
        return int(100 - (lines_changed - ideal) * 100 / (max_lines - ideal))
