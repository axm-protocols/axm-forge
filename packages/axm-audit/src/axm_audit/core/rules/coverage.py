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

_FULL_COVERAGE: int = 100  # Target coverage percentage for compact text output


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

    def _no_coverage_result(self, failures: list[dict[str, str]]) -> CheckResult:
        """Build the ``CheckResult`` returned when pytest-cov is not configured."""
        return CheckResult(
            rule_id=self.rule_id,
            passed=False,
            message="No coverage data (pytest-cov not configured)",
            severity=Severity.WARNING,
            details={"coverage": 0.0, "score": 0, "failures": failures},
            fix_hint="Add pytest-cov: uv add --dev pytest-cov",
        )

    @staticmethod
    def _build_text_parts(
        coverage_pct: float, failures: list[dict[str, str]]
    ) -> list[str]:
        """Build compact bullet lines for the coverage gap and up to 10 failures."""
        text_parts: list[str] = []
        if coverage_pct < _FULL_COVERAGE:
            text_parts.append(
                f"\u2022 cov {coverage_pct:.0f}% \u2192 {_FULL_COVERAGE}%"
            )
        for f in failures[:10]:
            short = f["test"].rsplit("::", 1)[-1]
            text_parts.append(f"\u2022 FAIL {short}")
        return text_parts

    @staticmethod
    def _build_message(
        coverage_pct: float, score: int, has_failures: bool, total_fails: int
    ) -> str:
        """Format the human-readable coverage message, with or without failures."""
        if has_failures:
            return f"Test coverage: {coverage_pct:.0f}% ({total_fails} test(s) failed)"
        return f"Test coverage: {coverage_pct:.0f}% ({score}/100)"

    def _report_to_result(self, report: TestReport) -> CheckResult:
        """Convert a ``TestReport`` to a ``CheckResult``.

        Builds a compact text summary with bullet lines for coverage gap
        (``• cov N% → 100%``) and up to 10 short failure names
        (``• FAIL test_name``).  Returns ``text=None`` when coverage is
        full and no failures exist.
        """
        coverage_pct = report.coverage if report.coverage is not None else 0.0
        score = int(coverage_pct)
        has_failures = report.failed > 0 or report.errors > 0
        passed = coverage_pct >= self.min_coverage and not has_failures
        total_fails = report.failed + report.errors

        failures: list[dict[str, str]] = [
            {"test": f.test, "traceback": f.message} for f in report.failures or []
        ]

        if report.coverage is None:
            return self._no_coverage_result(failures)

        message = self._build_message(coverage_pct, score, has_failures, total_fails)
        text_parts = self._build_text_parts(coverage_pct, failures)

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
            fix_hint=self._generate_fix_hints(has_failures, coverage_pct),
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
