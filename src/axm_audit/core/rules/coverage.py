"""Coverage rule — test coverage and failure detection via pytest-cov."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from axm_audit.core.rules.base import ProjectRule
from axm_audit.core.runner import run_in_project
from axm_audit.models.results import CheckResult, Severity

__all__ = ["TestCoverageRule"]

logger = logging.getLogger(__name__)


@dataclass
class TestCoverageRule(ProjectRule):
    """Check test coverage via pytest-cov.

    Scoring: coverage percentage directly (e.g., 90% → score 90).
    Pass threshold: 90%.
    """

    min_coverage: float = 90.0

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "QUALITY_COVERAGE"

    @property
    def category(self) -> str:
        """Scoring category for this rule."""
        return "testing"

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


def _collect_failed_lines(lines: list[str]) -> list[dict[str, str]]:
    """Parse FAILED lines from pytest output."""
    failures: list[dict[str, str]] = []
    for line in lines:
        if not line.startswith("FAILED "):
            continue
        parts = line[7:].split(" - ", 1)
        test_name = parts[0].strip()
        error_msg = parts[1].strip() if len(parts) > 1 else ""
        failures.append({"test": test_name, "traceback": error_msg})
    return failures


def _collect_tracebacks(
    lines: list[str],
    failures: list[dict[str, str]],
) -> None:
    """Attach traceback blocks to previously collected failures."""
    current_test: str | None = None
    current_tb: list[str] = []
    for line in lines:
        if line.startswith("_") and line.endswith("_"):
            if current_test:
                _attach_traceback(failures, current_test, current_tb)
            current_test = line.strip("_ ").strip()
            current_tb = []
        elif current_test:
            current_tb.append(line)

    if current_test:
        _attach_traceback(failures, current_test, current_tb)


def _extract_test_failures(stdout: str) -> list[dict[str, str]]:
    """Parse pytest stdout for FAILED test names and tracebacks.

    Args:
        stdout: Raw pytest output.

    Returns:
        List of dicts with 'test' and 'traceback' keys.
    """
    lines = stdout.split("\n")
    failures = _collect_failed_lines(lines)
    _collect_tracebacks(lines, failures)
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
