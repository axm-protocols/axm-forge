"""Quality rules — subprocess-based tool execution with JSON parsing."""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from axm_audit.core.rules.base import ProjectRule
from axm_audit.models.results import CheckResult, Severity


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
        """Check project linting with ruff."""
        src_path = project_path / "src"
        if not src_path.exists():
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="src/ directory not found",
                severity=Severity.ERROR,
            )

        result = subprocess.run(
            ["ruff", "check", "--output-format=json", str(src_path)],
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
        passed = score >= 80

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Lint score: {score}/100 ({issue_count} issues)",
            severity=Severity.WARNING if not passed else Severity.INFO,
            details={"issue_count": issue_count, "score": score},
            fix_hint="Run: ruff check --fix src/" if issue_count > 0 else None,
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
        """Check project type hints with mypy."""
        src_path = project_path / "src"
        if not src_path.exists():
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="src/ directory not found",
                severity=Severity.ERROR,
            )

        result = subprocess.run(
            ["mypy", "--no-error-summary", "--output", "json", str(src_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        error_count = 0
        if result.stdout.strip():
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    try:
                        entry = json.loads(line)
                        if entry.get("severity") == "error":
                            error_count += 1
                    except json.JSONDecodeError:
                        pass

        score = max(0, 100 - error_count * 5)
        passed = score >= 80

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Type score: {score}/100 ({error_count} errors)",
            severity=Severity.WARNING if not passed else Severity.INFO,
            details={"error_count": error_count, "score": score},
            fix_hint=(
                "Add type hints to functions and fix type errors"
                if error_count > 0
                else None
            ),
        )


@dataclass
class ComplexityRule(ProjectRule):
    """Analyse cyclomatic complexity via radon Python API.

    Scoring: 100 - (high_complexity_count * 10), min 0.
    High complexity = CC >= 10 (industry standard).
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "QUALITY_COMPLEXITY"

    def check(self, project_path: Path) -> CheckResult:
        """Check project complexity with radon."""
        from radon.complexity import cc_visit

        src_path = project_path / "src"
        if not src_path.exists():
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="src/ directory not found",
                severity=Severity.ERROR,
            )

        high_complexity_count = 0
        all_functions: list[dict[str, str | int]] = []

        for py_file in src_path.rglob("*.py"):
            try:
                source = py_file.read_text(encoding="utf-8")
                blocks = cc_visit(source)
            except (SyntaxError, UnicodeDecodeError):
                continue

            for block in blocks:
                cc: int = block.complexity
                if cc >= 10:
                    high_complexity_count += 1
                    all_functions.append(
                        {
                            "file": py_file.name,
                            "function": block.name,
                            "cc": cc,
                        }
                    )

        # Sort by complexity descending, take top 5
        top_offenders = sorted(all_functions, key=lambda x: x["cc"], reverse=True)[:5]

        score = max(0, 100 - high_complexity_count * 10)
        passed = score >= 80

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=(
                f"Complexity score: {score}/100 "
                f"({high_complexity_count} high-complexity functions)"
            ),
            severity=Severity.WARNING if not passed else Severity.INFO,
            details={
                "high_complexity_count": high_complexity_count,
                "top_offenders": top_offenders,
                "score": score,
            },
            fix_hint=(
                "Refactor complex functions into smaller units"
                if high_complexity_count > 0
                else None
            ),
        )
