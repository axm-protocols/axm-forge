from __future__ import annotations

from unittest.mock import Mock

from axm_audit.models.results import AuditResult


def _make_check(
    category: str | None, score: float | None, *, has_details: bool = True
) -> Mock:
    """Build a mock check with the given category and score."""
    check = Mock()
    check.category = category
    if has_details:
        check.details = {"score": score} if score is not None else {}
    else:
        check.details = None
    return check


def _make_result(checks: list[Mock]) -> AuditResult:
    """Build an AuditResult with only .checks populated."""
    result = Mock(spec=AuditResult)
    result.checks = checks
    # Bind the real property so the actual logic runs
    result.quality_score = AuditResult.quality_score.fget(result)  # type: ignore[attr-defined]
    return result


# ── Edge case: no scored checks → None ──────────────────────────────


class TestQualityScoreNoScoredChecks:
    """When no checks carry a usable score the property returns None."""

    def test_empty_checks_list(self) -> None:
        result = _make_result([])
        assert result.quality_score is None

    def test_checks_without_category(self) -> None:
        checks = [_make_check(category=None, score=80.0)]
        result = _make_result(checks)
        assert result.quality_score is None

    def test_checks_with_unknown_category(self) -> None:
        checks = [_make_check(category="unknown", score=80.0)]
        result = _make_result(checks)
        assert result.quality_score is None

    def test_checks_without_details(self) -> None:
        checks = [_make_check(category="lint", score=None, has_details=False)]
        result = _make_result(checks)
        assert result.quality_score is None

    def test_checks_with_details_but_no_score_key(self) -> None:
        checks = [_make_check(category="lint", score=None)]
        result = _make_result(checks)
        assert result.quality_score is None


# ── Edge case: single category only ─────────────────────────────────


class TestQualityScoreSingleCategory:
    """With a single category the score equals that category's average."""

    def test_single_lint_check(self) -> None:
        checks = [_make_check(category="lint", score=85.0)]
        result = _make_result(checks)
        assert result.quality_score == 85.0

    def test_single_category_multiple_checks_averaged(self) -> None:
        checks = [
            _make_check(category="lint", score=80.0),
            _make_check(category="lint", score=90.0),
        ]
        result = _make_result(checks)
        assert result.quality_score == 85.0

    def test_single_security_check(self) -> None:
        checks = [_make_check(category="security", score=70.0)]
        result = _make_result(checks)
        assert result.quality_score == 70.0


# ── Edge case: all scores zero ──────────────────────────────────────


class TestQualityScoreAllZero:
    """When every category scores 0 the result is 0.0."""

    def test_all_categories_zero(self) -> None:
        categories = [
            "lint",
            "type",
            "complexity",
            "security",
            "deps",
            "testing",
            "architecture",
            "practices",
        ]
        checks = [_make_check(category=cat, score=0.0) for cat in categories]
        result = _make_result(checks)
        assert result.quality_score == 0.0

    def test_single_category_zero(self) -> None:
        checks = [_make_check(category="lint", score=0.0)]
        result = _make_result(checks)
        assert result.quality_score == 0.0


# ── Unit: weighted average correctness ──────────────────────────────


class TestQualityScoreWeightedAverage:
    """Verify the weighted-average math with known inputs."""

    def test_two_categories_weighted(self) -> None:
        """lint (w=0.20) at 100, security (w=0.10) at 50.

        Expected: (100*0.20 + 50*0.10) / (0.20 + 0.10) = 25/0.30 = 83.3
        """
        checks = [
            _make_check(category="lint", score=100.0),
            _make_check(category="security", score=50.0),
        ]
        result = _make_result(checks)
        assert result.quality_score == 83.3

    def test_all_categories_perfect(self) -> None:
        categories = [
            "lint",
            "type",
            "complexity",
            "security",
            "deps",
            "testing",
            "architecture",
            "practices",
        ]
        checks = [_make_check(category=cat, score=100.0) for cat in categories]
        result = _make_result(checks)
        assert result.quality_score == 100.0

    def test_mixed_scored_and_unscored_checks(self) -> None:
        """Unscored checks (missing details/score) are ignored."""
        checks = [
            _make_check(category="lint", score=80.0),
            _make_check(category="lint", score=None),  # no score key
            _make_check(category="type", score=60.0),
            _make_check(category=None, score=90.0),  # no category
        ]
        result = _make_result(checks)
        # lint=80 (w=0.20), type=60 (w=0.15)
        # (80*0.20 + 60*0.15) / (0.20+0.15) = 25/0.35 ≈ 71.4
        assert result.quality_score == 71.4


# ── Unit: _collect_category_scores helper (post-refactor) ──────────


class TestCollectCategoryScores:
    """Tests for the extracted _collect_category_scores helper."""

    def test_groups_scores_by_category(self) -> None:
        from axm_audit.models.results import _collect_category_scores

        checks = [
            _make_check(category="lint", score=80.0),
            _make_check(category="lint", score=90.0),
            _make_check(category="type", score=70.0),
        ]
        result = _collect_category_scores(checks)
        assert result == {"lint": [80.0, 90.0], "type": [70.0]}

    def test_skips_invalid_checks(self) -> None:
        from axm_audit.models.results import _collect_category_scores

        checks = [
            _make_check(category=None, score=80.0),
            _make_check(category="unknown", score=80.0),
            _make_check(category="lint", score=None),
            _make_check(category="lint", score=None, has_details=False),
        ]
        result = _collect_category_scores(checks)
        assert result == {}

    def test_empty_checks(self) -> None:
        from axm_audit.models.results import _collect_category_scores

        result = _collect_category_scores([])
        assert result == {}
