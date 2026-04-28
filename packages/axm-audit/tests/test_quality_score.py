from __future__ import annotations

from unittest.mock import Mock

import pytest

from axm_audit.models.results import _CATEGORY_WEIGHTS, AuditResult


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
    result.quality_score = AuditResult.quality_score.fget(result)  # type: ignore[attr-defined]
    return result


SCORED_CATEGORIES = sorted(_CATEGORY_WEIGHTS)


# ── Invariants on the weights table itself ──────────────────────────


class TestWeightsTableInvariants:
    """Properties the weights dict must always satisfy."""

    def test_weights_sum_to_one(self) -> None:
        assert sum(_CATEGORY_WEIGHTS.values()) == pytest.approx(1.0, abs=1e-9)

    def test_all_weights_strictly_positive(self) -> None:
        assert all(w > 0 for w in _CATEGORY_WEIGHTS.values())

    def test_no_weight_exceeds_one(self) -> None:
        assert all(w <= 1.0 for w in _CATEGORY_WEIGHTS.values())


# ── Edge case: no scored checks → None ──────────────────────────────


class TestQualityScoreNoScoredChecks:
    """When no checks carry a usable score the property returns None."""

    def test_empty_checks_list(self) -> None:
        assert _make_result([]).quality_score is None

    def test_checks_without_category(self) -> None:
        checks = [_make_check(category=None, score=80.0)]
        assert _make_result(checks).quality_score is None

    def test_checks_with_unknown_category(self) -> None:
        checks = [_make_check(category="unknown", score=80.0)]
        assert _make_result(checks).quality_score is None

    def test_checks_without_details(self) -> None:
        checks = [_make_check(category="lint", score=None, has_details=False)]
        assert _make_result(checks).quality_score is None

    def test_checks_with_details_but_no_score_key(self) -> None:
        checks = [_make_check(category="lint", score=None)]
        assert _make_result(checks).quality_score is None

    def test_unscored_categories_ignored(self) -> None:
        """Categories absent from _CATEGORY_WEIGHTS contribute nothing."""
        checks = [
            _make_check(category="structure", score=0.0),
            _make_check(category="tooling", score=0.0),
        ]
        assert _make_result(checks).quality_score is None


# ── Property: range and identity ────────────────────────────────────


class TestQualityScoreRange:
    """Score always falls in [0, 100] when defined."""

    @pytest.mark.parametrize("category", SCORED_CATEGORIES)
    def test_perfect_single_category_is_100(self, category: str) -> None:
        checks = [_make_check(category=category, score=100.0)]
        assert _make_result(checks).quality_score == 100.0

    @pytest.mark.parametrize("category", SCORED_CATEGORIES)
    def test_zero_single_category_is_0(self, category: str) -> None:
        checks = [_make_check(category=category, score=0.0)]
        assert _make_result(checks).quality_score == 0.0

    def test_all_categories_perfect_is_100(self) -> None:
        checks = [_make_check(category=cat, score=100.0) for cat in SCORED_CATEGORIES]
        assert _make_result(checks).quality_score == 100.0

    def test_all_categories_zero_is_0(self) -> None:
        checks = [_make_check(category=cat, score=0.0) for cat in SCORED_CATEGORIES]
        assert _make_result(checks).quality_score == 0.0

    def test_score_within_bounds_for_arbitrary_inputs(self) -> None:
        checks = [
            _make_check(category="lint", score=42.0),
            _make_check(category="type", score=88.0),
            _make_check(category="security", score=17.0),
        ]
        score = _make_result(checks).quality_score
        assert score is not None
        assert 0.0 <= score <= 100.0


# ── Property: averaging within a category ───────────────────────────


class TestSingleCategoryAveraging:
    """Multiple checks in one category are averaged before weighting."""

    def test_single_check_passes_through(self) -> None:
        checks = [_make_check(category="lint", score=85.0)]
        assert _make_result(checks).quality_score == 85.0

    def test_multiple_checks_in_one_category_averaged(self) -> None:
        checks = [
            _make_check(category="lint", score=80.0),
            _make_check(category="lint", score=90.0),
        ]
        assert _make_result(checks).quality_score == 85.0

    def test_filtered_audit_returns_category_average(self) -> None:
        """With one category, weights cancel out: result == that average."""
        checks = [_make_check(category="security", score=70.0)]
        assert _make_result(checks).quality_score == 70.0


# ── Property: monotonicity ──────────────────────────────────────────


class TestMonotonicity:
    """Improving any category never lowers the composite."""

    def test_improving_one_category_does_not_decrease_score(self) -> None:
        before = [_make_check(category=cat, score=50.0) for cat in SCORED_CATEGORIES]
        score_before = _make_result(before).quality_score
        assert score_before is not None

        for category in SCORED_CATEGORIES:
            after = [
                _make_check(category=cat, score=100.0 if cat == category else 50.0)
                for cat in SCORED_CATEGORIES
            ]
            score_after = _make_result(after).quality_score
            assert score_after is not None
            assert score_after >= score_before, (
                f"raising {category} from 50 to 100 lowered score "
                f"({score_before} -> {score_after})"
            )

    def test_degrading_one_category_does_not_increase_score(self) -> None:
        before = [_make_check(category=cat, score=50.0) for cat in SCORED_CATEGORIES]
        score_before = _make_result(before).quality_score
        assert score_before is not None

        for category in SCORED_CATEGORIES:
            after = [
                _make_check(category=cat, score=0.0 if cat == category else 50.0)
                for cat in SCORED_CATEGORIES
            ]
            score_after = _make_result(after).quality_score
            assert score_after is not None
            assert score_after <= score_before


# ── Property: filtering and renormalization ─────────────────────────


class TestFilteredAuditRenormalization:
    """Missing categories must not penalize the score (filtered audits)."""

    def test_two_perfect_categories_yield_100(self) -> None:
        checks = [
            _make_check(category="lint", score=100.0),
            _make_check(category="security", score=100.0),
        ]
        assert _make_result(checks).quality_score == 100.0

    def test_unscored_and_unknown_inputs_are_ignored(self) -> None:
        checks = [
            _make_check(category="lint", score=80.0),
            _make_check(category="lint", score=None),
            _make_check(category=None, score=90.0),
            _make_check(category="unknown", score=50.0),
        ]
        assert _make_result(checks).quality_score == 80.0
