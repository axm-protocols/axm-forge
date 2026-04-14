"""Coverage rule — test coverage and failure detection via pytest-cov."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from axm_audit.core.rules.base import ProjectRule, register_rule
from axm_audit.core.test_runner import TestReport
from axm_audit.models.results import CheckResult, Severity

__all__ = ["TestCoverageRule"]

logger = logging.getLogger(__name__)

_FULL_COVERAGE: int = 100


@dataclass
@register_rule("testing")
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

    def check(self, project_path: Path) -> CheckResult:
        """Check test coverage and capture failures with pytest-cov.

        Delegates to ``run_tests(mode='compact')`` from the shared
        test runner for structured output, then converts the result
        to a ``CheckResult``.
        """
        from axm_audit.core.test_runner import run_tests

        report = run_tests(project_path, mode="compact", stop_on_first=False)
        return self._report_to_result(report)

    def _report_to_result(self, report: TestReport) -> CheckResult:
        """Convert a ``TestReport`` to a ``CheckResult``."""
        coverage_pct = report.coverage if report.coverage is not None else 0.0
        score = int(coverage_pct)
        has_failures = report.failed > 0 or report.errors > 0
        passed = coverage_pct >= self.min_coverage and not has_failures

        # Build failure details for backwards-compatible format
        failures: list[dict[str, str]] = [
            {"test": f.test, "traceback": f.message} for f in report.failures
        ]

        if report.coverage is None:
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="No coverage data (pytest-cov not configured)",
                severity=Severity.WARNING,
                details={"coverage": 0.0, "score": 0, "failures": failures},
                fix_hint="Add pytest-cov: uv add --dev pytest-cov",
            )

        if has_failures:
            total_fails = report.failed + report.errors
            message = (
                f"Test coverage: {coverage_pct:.0f}% ({total_fails} test(s) failed)"
            )
        else:
            message = f"Test coverage: {coverage_pct:.0f}% ({score}/100)"

        fix_hints = self._generate_fix_hints(has_failures, coverage_pct)

        text_parts: list[str] = []
        if coverage_pct < _FULL_COVERAGE:
            text_parts.append(
                f"     \u2022 Coverage: {coverage_pct:.1f}%"
                f" \u2192 target: {_FULL_COVERAGE}%"
            )
        for f in failures[:10]:
            text_parts.append(f"     \u2022 FAIL: {f['test']}")

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
            text="\n".join(text_parts) if text_parts else None,
            fix_hint=fix_hints,
        )

    def _generate_fix_hints(
        self, has_failures: bool, coverage_pct: float
    ) -> str | None:
        """Generate fix hints based on failures and coverage."""
        fix_hints: list[str] = []
        if has_failures:
            fix_hints.append("Fix failing tests")
        if coverage_pct < self.min_coverage:
            fix_hints.append(f"Increase test coverage to >= {self.min_coverage:.0f}%")
        return "; ".join(fix_hints) if fix_hints else None


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
