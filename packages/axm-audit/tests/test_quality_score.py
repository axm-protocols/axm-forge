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
    check.rule_id = f"mock_{category}"
    check.score = score
    if has_details:
        check.details = {} if score is None else {"placeholder": True}
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

    @pytest.mark.parametrize(
        "checks",
        [
            pytest.param([], id="empty"),
            pytest.param(
                [_make_check(category=None, score=80.0)],
                id="no_category",
            ),
            pytest.param(
                [_make_check(category="unknown", score=80.0)],
                id="unknown_category",
            ),
            pytest.param(
                [_make_check(category="lint", score=None, has_details=False)],
                id="no_details",
            ),
            pytest.param(
                [_make_check(category="lint", score=None)],
                id="details_without_score_key",
            ),
            pytest.param(
                [
                    _make_check(category="structure", score=0.0),
                    _make_check(category="tooling", score=0.0),
                ],
                id="unscored_categories_only",
            ),
        ],
    )
    def test_quality_score_is_none(self, checks: list[Mock]) -> None:
        assert _make_result(checks).quality_score is None


# ── Property: range and identity ────────────────────────────────────


class TestQualityScoreRange:
    """Score always falls in [0, 100] when defined."""

    @pytest.mark.parametrize("category", SCORED_CATEGORIES)
    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            pytest.param(100.0, 100.0, id="perfect"),
            pytest.param(0.0, 0.0, id="zero"),
        ],
    )
    def test_single_category_extreme_score(
        self, category: str, score: float, expected: float
    ) -> None:
        checks = [_make_check(category=category, score=score)]
        assert _make_result(checks).quality_score == expected

    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            pytest.param(100.0, 100.0, id="all_perfect"),
            pytest.param(0.0, 0.0, id="all_zero"),
        ],
    )
    def test_all_categories_uniform_score(self, score: float, expected: float) -> None:
        checks = [_make_check(category=cat, score=score) for cat in SCORED_CATEGORIES]
        assert _make_result(checks).quality_score == expected

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

    @pytest.mark.parametrize(
        ("scores", "expected_average"),
        [
            pytest.param((80.0, 90.0), 85.0, id="two_checks"),
            pytest.param((60.0, 80.0, 100.0), 80.0, id="three_checks"),
            pytest.param((0.0, 100.0), 50.0, id="extremes"),
        ],
    )
    def test_multiple_checks_in_one_category_averaged(
        self, scores: tuple[float, ...], expected_average: float
    ) -> None:
        checks = [_make_check(category="lint", score=s) for s in scores]
        assert _make_result(checks).quality_score == expected_average

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

    @pytest.mark.parametrize(
        "categories",
        [
            pytest.param(("lint", "security"), id="lint_security"),
            pytest.param(("lint", "type", "security"), id="three_categories"),
            pytest.param(tuple(SCORED_CATEGORIES[:1]), id="single_category"),
        ],
    )
    def test_perfect_categories_renormalize_to_100(
        self, categories: tuple[str, ...]
    ) -> None:
        checks = [_make_check(category=cat, score=100.0) for cat in categories]
        assert _make_result(checks).quality_score == 100.0

    def test_unscored_and_unknown_inputs_are_ignored(self) -> None:
        checks = [
            _make_check(category="lint", score=80.0),
            _make_check(category="lint", score=None),
            _make_check(category=None, score=90.0),
            _make_check(category="unknown", score=50.0),
        ]
        assert _make_result(checks).quality_score == 80.0
