"""Tests for redesigned scoring model — 8-category weighted score."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from axm_audit.models.results import CheckResult


class TestScoringRedesign:
    """Tests for the 8-category quality_score redesign."""

    def _make_check(self, rule_id: str, score: float) -> CheckResult:
        """Helper to create a CheckResult with a score."""
        from axm_audit.models.results import CheckResult

        return CheckResult(
            rule_id=rule_id,
            passed=True,
            message="",
            details={"score": score},
        )

    def _all_categories(self, score: float) -> list[CheckResult]:
        """Create checks for all 8 categories at a given score."""
        return [
            self._make_check("QUALITY_LINT", score),
            self._make_check("QUALITY_TYPE", score),
            self._make_check("QUALITY_COMPLEXITY", score),
            self._make_check("QUALITY_SECURITY", score),
            self._make_check("DEPS_AUDIT", score),
            self._make_check("DEPS_HYGIENE", score),
            self._make_check("QUALITY_COVERAGE", score),
            self._make_check("ARCH_COUPLING", score),
            self._make_check("PRACTICE_DOCSTRING", score),
            self._make_check("PRACTICE_BARE_EXCEPT", score),
            self._make_check("PRACTICE_SECURITY", score),
        ]

    def test_all_perfect_scores_100(self) -> None:
        """All 8 categories scoring 100 → quality_score=100."""
        from axm_audit.models.results import AuditResult

        result = AuditResult(checks=self._all_categories(100))
        assert result.quality_score == 100.0

    def test_mixed_scores_weighted(self) -> None:
        """Mixed scores should produce correct weighted average."""
        from axm_audit.models.results import AuditResult

        result = AuditResult(
            checks=[
                self._make_check("QUALITY_LINT", 80),  # 80 * 0.20 = 16
                self._make_check("QUALITY_TYPE", 60),  # 60 * 0.15 = 9
                self._make_check("QUALITY_COMPLEXITY", 100),  # 100 * 0.15 = 15
                self._make_check("QUALITY_SECURITY", 100),  # 100 * 0.10 = 10
                self._make_check("DEPS_AUDIT", 100),  # avg(100,100)*0.10 = 10
                self._make_check("DEPS_HYGIENE", 100),
                self._make_check("QUALITY_COVERAGE", 100),  # 100 * 0.15 = 15
                self._make_check("ARCH_COUPLING", 100),  # 100 * 0.10 = 10
                self._make_check("PRACTICE_DOCSTRING", 100),  # avg*0.05 = 5
                self._make_check("PRACTICE_BARE_EXCEPT", 100),
                self._make_check("PRACTICE_SECURITY", 100),
            ]
        )
        # 16 + 9 + 15 + 10 + 10 + 15 + 10 + 5 = 90
        assert result.quality_score is not None
        assert abs(result.quality_score - 90.0) < 1.0

    def test_no_scored_checks_returns_none(self) -> None:
        """No checks with scores → quality_score=None."""
        from axm_audit.models.results import AuditResult, CheckResult

        result = AuditResult(
            checks=[
                CheckResult(rule_id="FILE_EXISTS_README.md", passed=True, message=""),
            ]
        )
        assert result.quality_score is None

    def test_grade_a(self) -> None:
        """Score >= 90 → Grade A."""
        from axm_audit.models.results import AuditResult

        result = AuditResult(checks=self._all_categories(95))
        assert result.grade == "A"

    def test_grade_b(self) -> None:
        """Score >= 80 < 90 → Grade B."""
        from axm_audit.models.results import AuditResult

        result = AuditResult(checks=self._all_categories(85))
        assert result.grade == "B"

    def test_grade_f(self) -> None:
        """Score < 60 → Grade F."""
        from axm_audit.models.results import AuditResult

        result = AuditResult(checks=self._all_categories(30))
        assert result.grade == "F"
