"""Quality rules — linting, formatting, and type checking via subprocess."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from axm_audit.core.rules.base import PASS_THRESHOLD, ProjectRule
from axm_audit.core.runner import run_in_project
from axm_audit.models.results import CheckResult, Severity

__all__ = ["FormattingRule", "LintingRule", "TypeCheckRule"]


@dataclass
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
        src_path = project_path / "src"
        tests_path = project_path / "tests"

        if not src_path.exists():
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="src/ directory not found",
                severity=Severity.ERROR,
            )

        targets = [str(src_path)]
        if tests_path.exists():
            targets.append(str(tests_path))

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

        checked = "src/ tests/" if tests_path.exists() else "src/"
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
        src_path = project_path / "src"
        tests_path = project_path / "tests"

        if not src_path.exists():
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="src/ directory not found",
                severity=Severity.ERROR,
            )

        targets = [str(src_path)]
        if tests_path.exists():
            targets.append(str(tests_path))

        result = run_in_project(
            ["ruff", "format", "--check", *targets],
            project_path,
            capture_output=True,
            text=True,
            check=False,
        )

        # ruff format --check prints one file path per line to stdout
        unformatted_files = [
            line.strip()
            for line in result.stdout.strip().split("\n")
            if line.strip() and not line.startswith("error")
        ]
        unformatted_count = len(unformatted_files)

        score = max(0, 100 - unformatted_count * 5)
        passed = score >= PASS_THRESHOLD

        checked = "src/ tests/" if tests_path.exists() else "src/"
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


@dataclass
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
        src_path = project_path / "src"
        tests_path = project_path / "tests"

        if not src_path.exists():
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="src/ directory not found",
                severity=Severity.ERROR,
            )

        targets = [str(src_path)]
        if tests_path.exists():
            targets.append(str(tests_path))

        result = run_in_project(
            ["mypy", "--no-error-summary", "--output", "json", *targets],
            project_path,
            capture_output=True,
            text=True,
            check=False,
        )

        error_count = 0
        errors: list[dict[str, str | int]] = []
        if result.stdout.strip():
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    try:
                        entry = json.loads(line)
                        if entry.get("severity") == "error":
                            error_count += 1
                            errors.append(
                                {
                                    "file": entry.get("file", ""),
                                    "line": entry.get("line", 0),
                                    "message": entry.get("message", ""),
                                    "code": entry.get("code", ""),
                                }
                            )
                    except json.JSONDecodeError:
                        pass

        score = max(0, 100 - error_count * 5)
        passed = score >= PASS_THRESHOLD

        checked = "src/ tests/" if tests_path.exists() else "src/"
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
