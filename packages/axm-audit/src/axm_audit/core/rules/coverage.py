"""Coverage rule — test coverage and failure detection via pytest-cov."""

from __future__ import annotations

import logging
import math
import tomllib
from dataclasses import dataclass
from pathlib import Path

from axm_audit.core.rules.base import ProjectRule, register_rule
from axm_audit.core.test_runner import TestReport
from axm_audit.models.results import CheckResult, Severity

__all__ = ["TestCoverageRule", "read_coverage_config"]

logger = logging.getLogger(__name__)

_FULL_COVERAGE: int = 100  # Target coverage percentage for compact text output
_DEFAULT_MIN_COVERAGE: float = 90.0  # Pass threshold when unconfigured


def _safe_float(value: object, default: float) -> float:
    """Coerce ``value`` to a float in ``[0, 100]``, else return ``default``.

    Mirrors the robustness philosophy of ``coupling.safe_int``: a non-numeric
    type, a ``bool``, a ``NaN``/``inf``, or an out-of-bounds number all fall
    back to ``default`` rather than raising.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    coerced = float(value)
    if not math.isfinite(coerced) or coerced < 0 or coerced > _FULL_COVERAGE:
        return default
    return coerced


def read_coverage_config(project_path: Path) -> float:
    """Read ``[tool.axm-audit.coverage].min_coverage`` from pyproject.toml.

    Returns the configured pass threshold (bounds-checked to ``[0, 100]``),
    falling back to ``90.0`` on any error: missing file, missing section,
    missing key, malformed TOML, or an out-of-bounds / non-numeric value.
    Never raises.
    """
    pyproject = project_path / "pyproject.toml"
    if not pyproject.exists():
        return _DEFAULT_MIN_COVERAGE

    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return _DEFAULT_MIN_COVERAGE

    section = data.get("tool", {}).get("axm-audit", {}).get("coverage", {})
    return _safe_float(
        section.get("min_coverage", _DEFAULT_MIN_COVERAGE), _DEFAULT_MIN_COVERAGE
    )


@dataclass(frozen=True)
class _CoverageMetrics:
    """Derived coverage metrics for a single ``TestReport``."""

    effective: float
    coverage_pct: float
    score: int
    has_failures: bool
    passed: bool
    total_fails: int
    failures: list[dict[str, str]]

    @classmethod
    def from_report(
        cls, report: TestReport, default_min: float, min_coverage: float | None
    ) -> _CoverageMetrics:
        """Compute metrics from *report*, resolving the pass threshold."""
        effective = default_min if min_coverage is None else min_coverage
        coverage_pct = report.coverage if report.coverage is not None else 0.0
        has_failures = report.failed > 0 or report.errors > 0
        return cls(
            effective=effective,
            coverage_pct=coverage_pct,
            score=int(coverage_pct),
            has_failures=has_failures,
            passed=coverage_pct >= effective and not has_failures,
            total_fails=report.failed + report.errors,
            failures=[
                {"test": f.test, "traceback": f.message} for f in report.failures or []
            ],
        )


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

        The per-file gap list is derived from ``parse_coverage``'s
        filtered ``per_file`` map, which excludes ``__main__.py``
        entries by default (aligned with coverage.py's
        ``exclude_also`` convention).
        """
        from axm_audit.core.test_runner import run_tests

        effective = read_coverage_config(project_path)
        report = run_tests(project_path, mode="compact", stop_on_first=False)
        return self._report_to_result(report, min_coverage=effective)

    def _no_coverage_result(self, failures: list[dict[str, str]]) -> CheckResult:
        """Build the ``CheckResult`` returned when pytest-cov is not configured."""
        return CheckResult(
            rule_id=self.rule_id,
            passed=False,
            message="No coverage data (pytest-cov not configured)",
            severity=Severity.WARNING,
            score=0,
            details={"coverage": 0.0, "failures": failures},
            fix_hint="Add pytest-cov: uv add --dev pytest-cov",
        )

    def _timeout_result(self, failures: list[dict[str, str]]) -> CheckResult:
        """Build the ``CheckResult`` returned when the test run timed out.

        Coverage is reported as unmeasured (not a fabricated percentage
        derived from a truncated report) so a slow/contended run never
        masquerades as a real coverage gap.
        """
        return CheckResult(
            rule_id=self.rule_id,
            passed=False,
            message="Test run timed out — coverage not measured",
            severity=Severity.WARNING,
            score=0,
            details={"coverage": None, "failures": failures, "timed_out": True},
            fix_hint=(
                "Test suite exceeded the coverage-run timeout; rerun in "
                "isolation or raise the timeout. Coverage was not measured."
            ),
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

    def _report_to_result(
        self, report: TestReport, min_coverage: float | None = None
    ) -> CheckResult:
        """Convert a ``TestReport`` to a ``CheckResult``.

        ``min_coverage`` is the effective pass threshold resolved by ``check``
        from ``[tool.axm-audit.coverage]`` (defaults to ``self.min_coverage``
        when not supplied, preserving the no-config behavior). ``self`` is
        never mutated, so a shared rule instance never leaks one package's
        threshold into the next.

        Builds a compact text summary with bullet lines for coverage gap
        (``• cov N% → 100%``) and up to 10 short failure names
        (``• FAIL test_name``).  Returns ``text=None`` when coverage is
        full and no failures exist.
        """
        m = _CoverageMetrics.from_report(report, self.min_coverage, min_coverage)

        if report.timed_out:
            return self._timeout_result(m.failures)
        if report.coverage is None:
            return self._no_coverage_result(m.failures)

        text_parts = self._build_text_parts(m.coverage_pct, m.failures)
        return CheckResult(
            rule_id=self.rule_id,
            passed=m.passed,
            message=self._build_message(
                m.coverage_pct, m.score, m.has_failures, m.total_fails
            ),
            severity=Severity.WARNING if not m.passed else Severity.INFO,
            score=m.score,
            details={"coverage": m.coverage_pct, "failures": m.failures},
            text="\n".join(text_parts) if text_parts else None,
            fix_hint=self._generate_fix_hints(
                m.has_failures, m.coverage_pct, m.effective
            ),
        )

    def _generate_fix_hints(
        self, has_failures: bool, coverage_pct: float, min_coverage: float
    ) -> str | None:
        """Generate fix hints based on failures and the effective threshold."""
        fix_hints: list[str] = []
        if has_failures:
            fix_hints.append("Fix failing tests")
        if coverage_pct < min_coverage:
            fix_hints.append(f"Increase test coverage to >= {min_coverage:.0f}%")
        return "; ".join(fix_hints) if fix_hints else None
