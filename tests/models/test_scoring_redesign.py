"""Tests for redesigned scoring model — 6-category weighted score."""


class TestScoringRedesign:
    """Tests for the 6-category quality_score redesign."""

    def _make_check(self, rule_id: str, score: float):
        """Helper to create a CheckResult with a score."""
        from axm_audit.models.results import CheckResult

        return CheckResult(
            rule_id=rule_id,
            passed=True,
            message="",
            details={"score": score},
        )

    def _all_categories(self, score: float):
        """Create checks for all 6 categories at a given score."""
        return [
            self._make_check("QUALITY_LINT", score),
            self._make_check("QUALITY_TYPE", score),
            self._make_check("QUALITY_COMPLEXITY", score),
            self._make_check("QUALITY_SECURITY", score),
            self._make_check("DEPS_AUDIT", score),
            self._make_check("DEPS_HYGIENE", score),
            self._make_check("QUALITY_COVERAGE", score),
        ]

    def test_all_perfect_scores_100(self) -> None:
        """All 6 categories scoring 100 → quality_score=100."""
        from axm_audit.models.results import AuditResult

        result = AuditResult(checks=self._all_categories(100))
        assert result.quality_score == 100.0

    def test_mixed_scores_weighted(self) -> None:
        """Mixed scores should produce correct weighted average."""
        from axm_audit.models.results import AuditResult

        result = AuditResult(
            checks=[
                self._make_check("QUALITY_LINT", 80),  # 80 * 0.20 = 16
                self._make_check("QUALITY_TYPE", 60),  # 60 * 0.20 = 12
                self._make_check("QUALITY_COMPLEXITY", 100),  # 100 * 0.15 = 15
                self._make_check("QUALITY_SECURITY", 100),  # 100 * 0.15 = 15
                self._make_check("DEPS_AUDIT", 100),  # avg(100,100) * 0.15 = 15
                self._make_check("DEPS_HYGIENE", 100),
                self._make_check("QUALITY_COVERAGE", 100),  # 100 * 0.15 = 15
            ]
        )
        # 16 + 12 + 15 + 15 + 15 + 15 = 88
        assert result.quality_score is not None
        assert abs(result.quality_score - 88.0) < 1.0

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
