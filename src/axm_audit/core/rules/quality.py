"""Quality rules — subprocess-based tool execution with JSON parsing."""

import json
from dataclasses import dataclass
from pathlib import Path

from axm_audit.core.rules.base import ProjectRule
from axm_audit.core.runner import run_in_project
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
        passed = score >= 80

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
        passed = score >= 80

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
        try:
            from radon.complexity import cc_visit
        except ModuleNotFoundError:
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="radon is not installed — complexity analysis skipped",
                severity=Severity.ERROR,
                details={"score": 0},
                fix_hint=(
                    "Ensure axm-audit is properly installed: uv pip install axm-audit"
                ),
            )

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


@dataclass
class TestCoverageRule(ProjectRule):
    """Check test coverage via pytest-cov.

    Scoring: coverage percentage directly (e.g., 90% → score 90).
    Pass threshold: 80%.
    """

    min_coverage: float = 80.0

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "QUALITY_COVERAGE"

    def check(self, project_path: Path) -> CheckResult:
        """Check test coverage and capture failures with pytest-cov."""
        coverage_file = project_path / "coverage.json"

        # Run pytest with coverage and short tracebacks
        result = run_in_project(
            [
                "pytest",
                "--cov",
                "--cov-report=json",
                "--tb=short",
                "--no-header",
                "-q",
            ],
            project_path,
            capture_output=True,
            text=True,
            check=False,
        )

        # Extract test failures from stdout
        failures = _extract_test_failures(result.stdout)

        # Parse coverage.json
        if not coverage_file.exists():
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="No coverage data (pytest-cov not configured)",
                severity=Severity.WARNING,
                details={"coverage": 0.0, "score": 0, "failures": failures},
                fix_hint="Add pytest-cov: uv add --dev pytest-cov",
            )

        try:
            data = json.loads(coverage_file.read_text())
            coverage_pct = data.get("totals", {}).get("percent_covered", 0.0)
        except (json.JSONDecodeError, OSError):
            coverage_pct = 0.0

        score = int(coverage_pct)
        has_failures = len(failures) > 0
        passed = coverage_pct >= self.min_coverage and not has_failures

        if has_failures:
            message = (
                f"Test coverage: {coverage_pct:.0f}% ({len(failures)} test(s) failed)"
            )
        else:
            message = f"Test coverage: {coverage_pct:.0f}% ({score}/100)"

        fix_hints: list[str] = []
        if has_failures:
            fix_hints.append("Fix failing tests")
        if coverage_pct < self.min_coverage:
            fix_hints.append(f"Increase test coverage to >= {self.min_coverage:.0f}%")

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=message,
            severity=Severity.WARNING if not passed else Severity.INFO,
            details={
                "coverage": coverage_pct,
                "score": score,
                "failures": failures,
            },
            fix_hint=("; ".join(fix_hints) if fix_hints else None),
        )


def _extract_test_failures(stdout: str) -> list[dict[str, str]]:
    """Parse pytest stdout for FAILED test names and tracebacks.

    Args:
        stdout: Raw pytest output.

    Returns:
        List of dicts with 'test' and 'traceback' keys.
    """
    failures: list[dict[str, str]] = []
    lines = stdout.split("\n")

    # Collect FAILED lines: "FAILED tests/test_foo.py::test_bar - msg"
    for line in lines:
        if line.startswith("FAILED "):
            # Extract test name (before the " - " separator)
            parts = line[7:].split(" - ", 1)
            test_name = parts[0].strip()
            error_msg = parts[1].strip() if len(parts) > 1 else ""
            failures.append({"test": test_name, "traceback": error_msg})

    # If short traceback blocks exist, try to attach them
    # Format: "___ test_name ___" followed by traceback lines
    current_test: str | None = None
    current_tb: list[str] = []
    for line in lines:
        if line.startswith("_") and line.endswith("_"):
            # Save previous
            if current_test:
                _attach_traceback(failures, current_test, current_tb)
            # Parse test name from "____ test_name ____"
            current_test = line.strip("_ ").strip()
            current_tb = []
        elif current_test:
            current_tb.append(line)

    # Save last one
    if current_test:
        _attach_traceback(failures, current_test, current_tb)

    return failures


def _attach_traceback(
    failures: list[dict[str, str]],
    test_name: str,
    tb_lines: list[str],
) -> None:
    """Attach traceback lines to the matching failure entry."""
    tb_text = "\n".join(tb_lines).strip()
    if not tb_text:
        return
    for failure in failures:
        if test_name in failure["test"]:
            failure["traceback"] = tb_text
            return
