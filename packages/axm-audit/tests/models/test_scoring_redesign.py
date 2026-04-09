"""Tests for redesigned scoring model — 8-category weighted score."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from axm_audit.models.results import CheckResult


class TestScoringRedesign:
    """Tests for the 8-category quality_score redesign."""

    # Rule-id → scoring category mapping
    _RULE_CATEGORY: ClassVar[dict[str, str]] = {
        "QUALITY_LINT": "lint",
        "QUALITY_FORMAT": "lint",
        "QUALITY_DIFF_SIZE": "lint",
        "QUALITY_DEAD_CODE": "lint",
        "QUALITY_TYPE": "type",
        "QUALITY_COMPLEXITY": "complexity",
        "QUALITY_SECURITY": "security",
        "DEPS_AUDIT": "deps",
        "DEPS_HYGIENE": "deps",
        "QUALITY_COVERAGE": "testing",
        "ARCH_COUPLING": "architecture",
        "ARCH_CIRCULAR": "architecture",
        "ARCH_GOD_CLASS": "architecture",
        "ARCH_DUPLICATION": "architecture",
        "PRACTICE_DOCSTRING": "practices",
        "PRACTICE_BARE_EXCEPT": "practices",
        "PRACTICE_SECURITY": "practices",
        "PRACTICE_BLOCKING_IO": "practices",
        "PRACTICE_TEST_MIRROR": "practices",
    }

    def _make_check(self, rule_id: str, score: float) -> CheckResult:
        """Helper to create a CheckResult with a score and category."""
        from axm_audit.models.results import CheckResult

        return CheckResult(
            rule_id=rule_id,
            passed=True,
            message="",
            details={"score": score},
            category=self._RULE_CATEGORY.get(rule_id),
        )

    def _all_categories(self, score: float) -> list[CheckResult]:
        """Create checks for all scored categories at a given score."""
        return [
            self._make_check("QUALITY_LINT", score),
            self._make_check("QUALITY_FORMAT", score),
            self._make_check("QUALITY_DIFF_SIZE", score),
            self._make_check("QUALITY_TYPE", score),
            self._make_check("QUALITY_COMPLEXITY", score),
            self._make_check("QUALITY_SECURITY", score),
            self._make_check("DEPS_AUDIT", score),
            self._make_check("DEPS_HYGIENE", score),
            self._make_check("QUALITY_COVERAGE", score),
            self._make_check("ARCH_COUPLING", score),
            self._make_check("ARCH_CIRCULAR", score),
            self._make_check("ARCH_GOD_CLASS", score),
            self._make_check("ARCH_DUPLICATION", score),
            self._make_check("PRACTICE_DOCSTRING", score),
            self._make_check("PRACTICE_BARE_EXCEPT", score),
            self._make_check("PRACTICE_SECURITY", score),
            self._make_check("PRACTICE_BLOCKING_IO", score),
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
                self._make_check("QUALITY_LINT", 80),  # lint: avg(80,100,100)=93.3
                self._make_check("QUALITY_FORMAT", 100),
                self._make_check("QUALITY_DIFF_SIZE", 100),
                self._make_check("QUALITY_TYPE", 60),  # 60 * 0.15 = 9
                self._make_check("QUALITY_COMPLEXITY", 100),  # 100 * 0.15 = 15
                self._make_check("QUALITY_SECURITY", 100),  # 100 * 0.10 = 10
                self._make_check("DEPS_AUDIT", 100),  # avg(100,100)*0.10 = 10
                self._make_check("DEPS_HYGIENE", 100),
                self._make_check("QUALITY_COVERAGE", 100),  # 100 * 0.15 = 15
                self._make_check("ARCH_COUPLING", 100),  # avg*0.10 = 10
                self._make_check("ARCH_CIRCULAR", 100),
                self._make_check("ARCH_GOD_CLASS", 100),
                self._make_check("ARCH_DUPLICATION", 100),
                self._make_check("PRACTICE_DOCSTRING", 100),  # avg*0.05 = 5
                self._make_check("PRACTICE_BARE_EXCEPT", 100),
                self._make_check("PRACTICE_SECURITY", 100),
                self._make_check("PRACTICE_BLOCKING_IO", 100),
            ]
        )
        # lint: avg(80,100,100)=93.33 * 0.20 = 18.67
        # types: 60 * 0.15 = 9  |  complexity: 100*0.15=15
        # security: 100*0.10=10  |  deps: avg(100,100)*0.10=10
        # testing: 100*0.15=15  |  architecture: avg(100,100,100,100)*0.10=10
        # practices: avg(100,100,100,100,100)*0.05=5
        # Total: 18.67 + 9 + 15 + 10 + 10 + 15 + 10 + 5 = 92.67
        assert result.quality_score is not None
        assert abs(result.quality_score - 92.7) < 1.0

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
