"""Tests for audit models."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from unittest.mock import Mock

import pytest
from _registry_helpers import (
    SCORED_CATEGORIES,
    build_rule_category_map,
    scored_rule_ids,
)
from pydantic import ValidationError

from axm_audit.formatters import format_agent, format_report
from axm_audit.models.results import (
    _CATEGORY_WEIGHTS,
    EXTRA_NONSCORED_CATEGORIES,
    AuditResult,
    CheckResult,
    Severity,
    collect_category_scores,
)
from axm_audit.models.results import (
    SCORED_CATEGORIES as RESULTS_SCORED_CATEGORIES,
)
from tests.unit._helpers import _RULE_CATEGORY

# ---------------------------------------------------------------------------
# Original CheckResult / AuditResult basics
# ---------------------------------------------------------------------------


class TestCheckResult:
    """Tests for CheckResult model."""

    @pytest.mark.parametrize(
        ("passed", "message"),
        [
            pytest.param(True, "pyproject.toml exists", id="passed"),
            pytest.param(False, "README.md not found", id="failed"),
        ],
    )
    def test_check_result_passed_flag(self, passed: bool, message: str) -> None:
        """CheckResult.passed mirrors the constructor argument."""
        result = CheckResult(rule_id="FILE_EXISTS", passed=passed, message=message)
        assert result.passed is passed
        assert result.rule_id == "FILE_EXISTS"

    def test_audit_result_creation(self):
        """Test creating an AuditResult instance."""
        from axm_audit.models import AuditResult, CheckResult

        check = CheckResult(rule_id="TEST", passed=True, message="Test")
        result = AuditResult(checks=[check])

        assert result.total == 1
        assert result.success is True

    def test_audit_result_failure(self) -> None:
        """Audit with some checks failed."""
        from axm_audit.models.results import AuditResult, CheckResult

        checks = [
            CheckResult(rule_id="F1", passed=True, message="OK"),
            CheckResult(rule_id="F2", passed=False, message="FAIL"),
        ]
        result = AuditResult(checks=checks)
        assert result.success is False
        assert result.total == 2
        assert result.failed == 1

    def test_json_serialization(self) -> None:
        """AuditResult should serialize to valid JSON for Agents."""
        from axm_audit.models.results import AuditResult, CheckResult

        result = AuditResult(
            checks=[CheckResult(rule_id="TEST", passed=True, message="OK")]
        )
        data = json.loads(result.model_dump_json())
        assert "checks" in data
        assert "success" in data
        assert data["success"] is True

    def test_audit_result_quality_score(self):
        """Test that quality scoring works."""
        from axm_audit.models import AuditResult, CheckResult

        checks = [
            CheckResult(
                rule_id="QUALITY_LINT",
                passed=True,
                message="Pass",
                score=90,
                category="lint",
            ),
            CheckResult(
                rule_id="QUALITY_TYPE",
                passed=False,
                message="Fail",
                score=50,
                category="type",
            ),
        ]
        result = AuditResult(checks=checks)

        assert result.quality_score is not None
        assert 0 <= result.quality_score <= 100

    def test_audit_result_grade(self):
        """Test that letter grading works."""
        from axm_audit.models import AuditResult, CheckResult

        checks = [
            CheckResult(
                rule_id="QUALITY_LINT",
                passed=True,
                message="Pass",
                score=95,
                category="lint",
            )
        ]
        result = AuditResult(checks=checks)

        assert result.grade in ["A", "B", "C", "D", "F"]


class TestRegistryDerivedScoring:
    """Scoring tests that derive rule lists from get_registry()."""

    def test_all_perfect_scores_100(self) -> None:
        """All scored rules at 100 via registry -> quality_score == 100.0."""
        category_map = build_rule_category_map()
        checks = [_make_check_with_map(rid, 100, category_map) for rid in category_map]
        result = AuditResult(checks=checks)
        assert result.quality_score == 100.0

    def test_all_zero_scores_grade_f(self) -> None:
        """All scored rules at 0 via registry -> grade == 'F'."""
        category_map = build_rule_category_map()
        checks = [_make_check_with_map(rid, 0, category_map) for rid in category_map]
        result = AuditResult(checks=checks)
        assert result.quality_score == pytest.approx(0.0, abs=0.1)
        assert result.grade == "F"

    def test_registry_covers_all_scored_categories(self) -> None:
        """Registry must provide at least one rule per scored category."""
        category_map = build_rule_category_map()
        covered = set(category_map.values())
        missing = SCORED_CATEGORIES - covered
        assert not missing, f"Scored categories missing from registry: {missing}"

    def test_rule_addition_no_test_change(self) -> None:
        """Adding a rule to the registry doesn't break scoring tests.

        This is structural: the test itself proves resilience because
        it derives everything from the registry. If a new rule is added,
        it will be automatically included in the checks list.
        """
        category_map = build_rule_category_map()
        assert len(category_map) > 0, "Registry should have at least one scored rule"
        checks = [_make_check_with_map(rid, 100, category_map) for rid in category_map]
        result = AuditResult(checks=checks)
        assert result.quality_score == 100.0

    def test_scored_rule_ids_non_empty(self) -> None:
        """scored_rule_ids must return a non-empty list."""
        ids = scored_rule_ids()
        assert len(ids) > 0
        # Each ID should be a non-empty string
        for rid in ids:
            assert isinstance(rid, str)
            assert len(rid) > 0


def _make_check_with_map(
    rule_id: str, score: float, category_map: dict[str, str]
) -> CheckResult:
    """Create a CheckResult with score and category from the registry map."""
    return CheckResult(
        rule_id=rule_id,
        passed=True,
        message="",
        score=int(score),
        category=category_map.get(rule_id),
    )


# ---------------------------------------------------------------------------
# Categories module-level invariants (from test_results_categories.py)
# ---------------------------------------------------------------------------


def test_scored_categories_match_weights() -> None:
    assert RESULTS_SCORED_CATEGORIES == frozenset(_CATEGORY_WEIGHTS)


def test_extra_nonscored_categories_are_disjoint() -> None:
    assert RESULTS_SCORED_CATEGORIES.isdisjoint(EXTRA_NONSCORED_CATEGORIES)


def _make_check_formula(rule_id: str, score: float) -> CheckResult:
    """Create a CheckResult with a score and the registry-derived category."""
    return CheckResult(
        rule_id=rule_id,
        passed=True,
        message="",
        score=int(score),
        category=_RULE_CATEGORY.get(rule_id),
    )


def _all_categories(score: float) -> list[CheckResult]:
    """Create checks for every registered scored rule at the given score."""
    return [_make_check_formula(rid, score) for rid in _RULE_CATEGORY]


class TestRegistryIntegration:
    """Sanity checks tying scoring behavior back to the rule registry."""

    def test_every_registered_rule_has_category(self) -> None:
        """Every rule in the registry must expose a non-empty category."""
        from axm_audit.core.rules.base import get_registry

        for category, rule_classes in get_registry().items():
            for cls in rule_classes:
                has_code = hasattr(cls.__init__, "__code__")
                rule = (
                    cls()
                    if not has_code or cls.__init__.__code__.co_varnames == ("self",)
                    else None
                )
                if rule is None:
                    continue
                assert rule.category, (
                    f"Rule {rule.rule_id} has empty category "
                    f"(expected registry category: {category})"
                )

    def test_all_scored_rules_at_100_yields_100(self) -> None:
        """Anti-drop regression: every registered scored rule contributes.

        Builds an AuditResult with ALL scored rules at 100 and asserts the
        score is exactly 100 (a missing rule would shift the weighted mean).
        """
        result = AuditResult(checks=_all_categories(100))
        assert result.quality_score == 100.0


# 3 categories, weight_sum = 0.20 + 0.15 + 0.15 = 0.50.
# Normalized: (80*0.20 + 60*0.15 + 100*0.15) / 0.50 = 80.0.
_PARTIAL_CHECKS: list[tuple[str, int]] = [
    ("QUALITY_LINT", 80),
    ("QUALITY_TYPE", 60),
    ("QUALITY_COMPLEXITY", 100),
]

# Lint-only audit: all checks share the same category, score equals the
# category mean — avg(94, 100, 95) ≈ 96.33.
_LINT_ONLY_CHECKS: list[tuple[str, int]] = [
    ("QUALITY_LINT", 94),
    ("QUALITY_FORMAT", 100),
    ("QUALITY_DEAD_CODE", 95),
]

# Mixed audit spanning every category at varying scores. Hand-computed to
# ≈ 92.7 — lint avg(80,100,100)*0.20 + type 60*0.15 + complexity 100*0.15
# + security 100*0.10 + deps avg(100,100)*0.10 + testing 100*0.15
# + arch avg(100,100,100,100)*0.10 + practices avg(100,100,100,100,100)*0.05.
_MIXED_CHECKS: list[tuple[str, int]] = [
    ("QUALITY_LINT", 80),
    ("QUALITY_FORMAT", 100),
    ("QUALITY_DIFF_SIZE", 100),
    ("QUALITY_TYPE", 60),
    ("QUALITY_COMPLEXITY", 100),
    ("QUALITY_SECURITY", 100),
    ("DEPS_AUDIT", 100),
    ("DEPS_HYGIENE", 100),
    ("QUALITY_COVERAGE", 100),
    ("ARCH_COUPLING", 100),
    ("ARCH_CIRCULAR", 100),
    ("ARCH_GOD_CLASS", 100),
    ("ARCH_DUPLICATION", 100),
    ("PRACTICE_DOCSTRING", 100),
    ("PRACTICE_BARE_EXCEPT", 100),
    ("PRACTICE_SECURITY", 100),
    ("PRACTICE_BLOCKING_IO", 100),
]


@pytest.mark.parametrize(
    ("score_inputs", "expected"),
    [
        pytest.param(
            [("QUALITY_COVERAGE", 100)],
            100.0,
            id="single_check_returns_its_score",
        ),
        pytest.param(_PARTIAL_CHECKS, 80.0, id="partial_normalized"),
        pytest.param(_LINT_ONLY_CHECKS, 96.33, id="lint_only_category_mean"),
        pytest.param(_MIXED_CHECKS, 92.7, id="mixed_weighted_average"),
    ],
)
def test_quality_score_weighted_average(
    score_inputs: list[tuple[str, int]],
    expected: float,
) -> None:
    """quality_score normalizes by weight_sum across the present categories."""
    result = AuditResult(
        checks=[_make_check_formula(rid, score) for rid, score in score_inputs],
    )
    assert result.quality_score is not None
    assert abs(result.quality_score - expected) < 1.0


@pytest.mark.parametrize(
    "checks",
    [
        pytest.param([], id="no_checks"),
        pytest.param(
            [CheckResult(rule_id="FILE_EXISTS_README.md", passed=True, message="")],
            id="check_without_category_or_score",
        ),
    ],
)
def test_quality_score_none_without_scored_checks(
    checks: list[CheckResult],
) -> None:
    """quality_score (and grade) is None when no check carries a score/category."""
    result = AuditResult(checks=checks)
    assert result.quality_score is None
    assert result.grade is None


@pytest.mark.parametrize(
    ("score", "expected_grade"),
    [
        pytest.param(100, "A", id="100_grade_a"),
        pytest.param(95, "A", id="95_grade_a"),
        pytest.param(85, "B", id="85_grade_b"),
        pytest.param(75, "C", id="75_grade_c"),
        pytest.param(65, "D", id="65_grade_d"),
        pytest.param(30, "F", id="30_grade_f"),
        pytest.param(0, "F", id="0_grade_f"),
    ],
)
def test_grade_thresholds(score: int, expected_grade: str) -> None:
    """grade derives from quality_score via fixed thresholds (A/B/C/D/F)."""
    result = AuditResult(checks=_all_categories(score))
    assert result.grade == expected_grade


# ---------------------------------------------------------------------------
# Quality score with mocked checks (from test_quality_score.py)
# ---------------------------------------------------------------------------


def _make_check_mock(
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
    result.quality_score = AuditResult.quality_score.fget(result)
    return result


_SCORED_CATEGORIES_SORTED = sorted(_CATEGORY_WEIGHTS)


# ── Invariants on the weights table itself ──────────────────────────


class TestWeightsTableInvariants:
    """Properties the weights dict must always satisfy."""

    def test_weights_sum_to_one(self) -> None:
        assert sum(_CATEGORY_WEIGHTS.values()) == pytest.approx(1.0, abs=1e-9)

    @pytest.mark.parametrize(
        "predicate",
        [
            pytest.param(lambda w: w > 0, id="strictly_positive"),
            pytest.param(lambda w: w <= 1.0, id="at_most_one"),
        ],
    )
    def test_weight_bounds(self, predicate: Callable[[float], bool]) -> None:
        assert all(predicate(w) for w in _CATEGORY_WEIGHTS.values())


# ── Edge case: no scored checks → None ──────────────────────────────


class TestQualityScoreNoScoredChecks:
    """When no checks carry a usable score the property returns None."""

    @pytest.mark.parametrize(
        "checks",
        [
            pytest.param([], id="empty"),
            pytest.param(
                [_make_check_mock(category=None, score=80.0)],
                id="no_category",
            ),
            pytest.param(
                [_make_check_mock(category="unknown", score=80.0)],
                id="unknown_category",
            ),
            pytest.param(
                [_make_check_mock(category="lint", score=None, has_details=False)],
                id="no_details",
            ),
            pytest.param(
                [_make_check_mock(category="lint", score=None)],
                id="details_without_score_key",
            ),
            pytest.param(
                [
                    _make_check_mock(category="structure", score=0.0),
                    _make_check_mock(category="tooling", score=0.0),
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

    @pytest.mark.parametrize("category", _SCORED_CATEGORIES_SORTED)
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
        checks = [_make_check_mock(category=category, score=score)]
        assert _make_result(checks).quality_score == expected

    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            pytest.param(100.0, 100.0, id="all_perfect"),
            pytest.param(0.0, 0.0, id="all_zero"),
        ],
    )
    def test_all_categories_uniform_score(self, score: float, expected: float) -> None:
        checks = [
            _make_check_mock(category=cat, score=score)
            for cat in _SCORED_CATEGORIES_SORTED
        ]
        assert _make_result(checks).quality_score == expected

    def test_score_within_bounds_for_arbitrary_inputs(self) -> None:
        checks = [
            _make_check_mock(category="lint", score=42.0),
            _make_check_mock(category="type", score=88.0),
            _make_check_mock(category="security", score=17.0),
        ]
        score = _make_result(checks).quality_score
        assert score is not None
        assert 0.0 <= score <= 100.0


# ── Property: averaging within a category ───────────────────────────


class TestSingleCategoryAveraging:
    """Multiple checks in one category are averaged before weighting."""

    def test_single_check_passes_through(self) -> None:
        checks = [_make_check_mock(category="lint", score=85.0)]
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
        checks = [_make_check_mock(category="lint", score=s) for s in scores]
        assert _make_result(checks).quality_score == expected_average

    def test_filtered_audit_returns_category_average(self) -> None:
        """With one category, weights cancel out: result == that average."""
        checks = [_make_check_mock(category="security", score=70.0)]
        assert _make_result(checks).quality_score == 70.0


# ── Property: monotonicity ──────────────────────────────────────────


class TestMonotonicity:
    """Improving any category never lowers the composite."""

    def test_improving_one_category_does_not_decrease_score(self) -> None:
        before = [
            _make_check_mock(category=cat, score=50.0)
            for cat in _SCORED_CATEGORIES_SORTED
        ]
        score_before = _make_result(before).quality_score
        assert score_before is not None

        for category in _SCORED_CATEGORIES_SORTED:
            after = [
                _make_check_mock(category=cat, score=100.0 if cat == category else 50.0)
                for cat in _SCORED_CATEGORIES_SORTED
            ]
            score_after = _make_result(after).quality_score
            assert score_after is not None
            assert score_after >= score_before, (
                f"raising {category} from 50 to 100 lowered score "
                f"({score_before} -> {score_after})"
            )

    def test_degrading_one_category_does_not_increase_score(self) -> None:
        before = [
            _make_check_mock(category=cat, score=50.0)
            for cat in _SCORED_CATEGORIES_SORTED
        ]
        score_before = _make_result(before).quality_score
        assert score_before is not None

        for category in _SCORED_CATEGORIES_SORTED:
            after = [
                _make_check_mock(category=cat, score=0.0 if cat == category else 50.0)
                for cat in _SCORED_CATEGORIES_SORTED
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
            pytest.param(tuple(_SCORED_CATEGORIES_SORTED[:1]), id="single_category"),
        ],
    )
    def test_perfect_categories_renormalize_to_100(
        self, categories: tuple[str, ...]
    ) -> None:
        checks = [_make_check_mock(category=cat, score=100.0) for cat in categories]
        assert _make_result(checks).quality_score == 100.0

    def test_unscored_and_unknown_inputs_are_ignored(self) -> None:
        checks = [
            _make_check_mock(category="lint", score=80.0),
            _make_check_mock(category="lint", score=None),
            _make_check_mock(category=None, score=90.0),
            _make_check_mock(category="unknown", score=50.0),
        ]
        assert _make_result(checks).quality_score == 80.0


# ---------------------------------------------------------------------------
# CheckResult typed score (from test_check_result_score.py)
# ---------------------------------------------------------------------------


def test_check_result_has_typed_score() -> None:
    result = CheckResult(rule_id="r", passed=True, message="ok", score=85)
    assert result.score == 85
    assert isinstance(result.score, int)


def test_check_result_score_validation() -> None:
    with pytest.raises(ValidationError):
        CheckResult(rule_id="r", passed=True, message="ok", score=150)
    with pytest.raises(ValidationError):
        CheckResult(rule_id="r", passed=True, message="ok", score=-1)


def test_check_result_score_default_none() -> None:
    result = CheckResult(rule_id="r", passed=True, message="ok")
    assert result.score is None


def test_collect_category_scores_reads_typed_score() -> None:
    check = CheckResult(
        rule_id="r", passed=True, message="ok", category="lint", score=80
    )
    assert collect_category_scores([check]) == {"lint": [80.0]}


def test_collect_category_scores_warns_on_missing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    check = CheckResult(
        rule_id="my_rule", passed=True, message="ok", category="lint", score=None
    )
    with caplog.at_level(logging.WARNING):
        result = collect_category_scores([check])
    assert result == {}
    assert any(
        record.levelno == logging.WARNING and "my_rule" in record.getMessage()
        for record in caplog.records
    )


def test_collect_category_scores_no_warn_for_unscored_category(
    caplog: pytest.LogCaptureFixture,
) -> None:
    check = CheckResult(
        rule_id="r", passed=True, message="ok", category="structure", score=None
    )
    with caplog.at_level(logging.WARNING):
        collect_category_scores([check])
    assert not any(record.levelno == logging.WARNING for record in caplog.records)


# ---------------------------------------------------------------------------
# CheckResult text field (from test_check_result_text.py)
# ---------------------------------------------------------------------------


def test_check_result_text_field() -> None:
    """CheckResult accepts and stores a `text` field."""
    cr = CheckResult(rule_id="X", passed=False, message="m", text="detail")
    assert cr.text == "detail"


def test_check_result_text_none_default() -> None:
    """CheckResult.text defaults to None when omitted."""
    cr = CheckResult(rule_id="X", passed=True, message="m")
    assert cr.text is None


def test_format_agent_uses_text() -> None:
    """format_agent() output contains the text from checks."""
    checks = [
        CheckResult(
            rule_id="QUALITY_LINT",
            passed=False,
            message="3 issues",
            text="    • [F401] foo.py:1: unused import",
            score=70,
            details={"issues": []},
        ),
    ]
    audit = AuditResult(
        checks=checks,
        project_path="/tmp/fake",
    )

    out = format_agent(audit)
    failed_entries = out["failed"]
    assert len(failed_entries) == 1
    assert failed_entries[0]["text"] == "    • [F401] foo.py:1: unused import"


def test_passed_rule_text_none_fallback_message() -> None:
    """Passed rule with text=None: format_agent falls back on message."""
    checks = [
        CheckResult(
            rule_id="QUALITY_LINT",
            passed=True,
            message="All clear",
            score=100,
        ),
    ]
    audit = AuditResult(
        checks=checks,
        project_path="/tmp/fake",
    )

    out = format_agent(audit)
    # Passed checks still render with message
    assert any("All clear" in str(p) for p in out["passed"])


def test_no_details_no_text_no_crash() -> None:
    """Rule with details=None and text=None renders gracefully."""
    checks = [
        CheckResult(
            rule_id="STRUCT_FILE",
            passed=False,
            message="Missing src/",
            severity=Severity.ERROR,
            details=None,
            text=None,
        ),
    ]
    audit = AuditResult(
        checks=checks,
        project_path="/tmp/fake",
    )

    # Neither formatter should crash
    agent_out = format_agent(audit)
    assert len(agent_out["failed"]) == 1

    report_out = format_report(audit)
    assert isinstance(report_out, str)
    assert "Missing src/" in report_out


# ---------------------------------------------------------------------------
# AuditResult round-trip (from test_audit_result_round_trip.py)
# ---------------------------------------------------------------------------


def _check_rt(score: float, category: str = "lint", rule_id: str = "r1") -> CheckResult:
    return CheckResult(
        rule_id=rule_id,
        passed=True,
        message="ok",
        category=category,
        score=int(score),
    )


def test_audit_result_round_trip() -> None:
    ar = AuditResult(checks=[_check_rt(88)])
    # Pure round-trip across the persistent (non-computed) fields: dump and
    # re-validate without the __init__ hack popping keys.
    dump = ar.model_dump(
        exclude={"success", "total", "failed", "quality_score", "grade"}
    )
    restored = AuditResult.model_validate(dump)
    assert restored == ar
    assert ar.quality_score == 88.0
    assert restored.quality_score == 88.0


def test_audit_result_quality_score_computed_from_checks() -> None:
    ar = AuditResult(checks=[_check_rt(80, rule_id="r1"), _check_rt(100, rule_id="r2")])
    assert ar.quality_score == 90.0


def test_audit_result_rejects_quality_score_kwarg() -> None:
    with pytest.raises(ValidationError):
        AuditResult(quality_score=85)  # type: ignore[call-arg]


def test_audit_result_rejects_grade_kwarg() -> None:
    with pytest.raises(ValidationError):
        AuditResult(grade="A")  # type: ignore[call-arg]


def test_audit_result_no_override_attrs_after_migration() -> None:
    private_attrs = AuditResult.__private_attributes__
    assert "_override_quality_score" not in private_attrs
    assert "_override_grade" not in private_attrs


def test_audit_result_empty_checks_quality_score_none() -> None:
    ar = AuditResult(checks=[])
    assert ar.quality_score is None
    assert ar.grade is None


# ---------------------------------------------------------------------------
# --- Public-API tests (merged from test_audit_result_score_public_api.py) ---
# ---------------------------------------------------------------------------


def _public_api_check(
    rule_id: str, category: str, score: int, *, passed: bool = True
) -> CheckResult:
    return CheckResult(
        rule_id=rule_id,
        passed=passed,
        message=f"{rule_id}: {score}/100",
        category=category,
        score=score,
    )


def test_audit_result_score_aggregates_within_category() -> None:
    """Multiple checks in one category are averaged before weighting."""
    checks = [
        _public_api_check("lint_a", "lint", 100),
        _public_api_check("lint_b", "lint", 80),
    ]
    result = AuditResult(checks=checks)
    assert result.quality_score is not None
    assert abs(result.quality_score - 90.0) < 0.1


def test_audit_result_score_combines_categories_within_bounds() -> None:
    """Combining categories yields a score in [min(cat_avg), max(cat_avg)]."""
    checks = [
        _public_api_check("lint_a", "lint", 100),
        _public_api_check("lint_b", "lint", 80),
        _public_api_check("sec_a", "security", 60, passed=False),
    ]
    result = AuditResult(checks=checks)
    assert result.quality_score is not None
    assert 60.0 <= result.quality_score <= 90.0


def test_audit_result_score_normalizes_partial_categories() -> None:
    """A single-category audit is not penalized for missing categories."""
    checks = [_public_api_check("lint_a", "lint", 90)]
    result = AuditResult(checks=checks)
    assert result.quality_score == 90.0
