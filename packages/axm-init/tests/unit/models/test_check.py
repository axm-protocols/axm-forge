"""Unit tests for check models: Grade, CheckResult, ProjectResult, CategoryScore.

TDD RED — these tests define the expected API for models/check.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

# ─────────────────────────────────────────────────────────────────────────────
# Imports (will fail until models/check.py exists)
# ─────────────────────────────────────────────────────────────────────────────
from axm_init.models.check import (
    CategoryScore,
    CheckResult,
    Grade,
    ProjectResult,
    compute_grade,
)

# ─────────────────────────────────────────────────────────────────────────────
# Grade computation
# ─────────────────────────────────────────────────────────────────────────────


class TestGradeEnum:
    """Grade enum values."""

    def test_grade_a(self) -> None:
        assert Grade.A == "A"

    def test_grade_f(self) -> None:
        assert Grade.F == "F"

    def test_all_grades(self) -> None:
        assert set(Grade) == {Grade.A, Grade.B, Grade.C, Grade.D, Grade.F}


class TestComputeGrade:
    """Grade boundaries: A≥90, B≥75, C≥60, D≥40, F<40."""

    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            pytest.param(100, Grade.A, id="100_is_a"),
            pytest.param(90, Grade.A, id="90_is_a"),
            pytest.param(89, Grade.B, id="89_is_b"),
            pytest.param(75, Grade.B, id="75_is_b"),
            pytest.param(74, Grade.C, id="74_is_c"),
            pytest.param(60, Grade.C, id="60_is_c"),
            pytest.param(59, Grade.D, id="59_is_d"),
            pytest.param(40, Grade.D, id="40_is_d"),
            pytest.param(39, Grade.F, id="39_is_f"),
            pytest.param(0, Grade.F, id="0_is_f"),
        ],
    )
    def test_compute_grade(self, score: int, expected: Grade) -> None:
        assert compute_grade(score) == expected


# ─────────────────────────────────────────────────────────────────────────────
# CheckResult model
# ─────────────────────────────────────────────────────────────────────────────


class TestCheckResult:
    """CheckResult must carry all diagnostic info."""

    def test_passing_check(self) -> None:
        c = CheckResult(
            name="pyproject.exists",
            category="pyproject",
            passed=True,
            weight=5,
            message="pyproject.toml found",
            details=[],
            fix="",
        )
        assert c.passed is True
        assert c.weight == 5
        assert c.earned == 5

    def test_failing_check_earned_zero(self) -> None:
        c = CheckResult(
            name="pyproject.mypy",
            category="pyproject",
            passed=False,
            weight=4,
            message="MyPy config incomplete",
            details=["Missing: pretty = true"],
            fix="Add pretty = true to [tool.mypy]",
        )
        assert c.earned == 0
        assert c.fix != ""

    def test_details_is_list(self) -> None:
        c = CheckResult(
            name="x",
            category="y",
            passed=False,
            weight=1,
            message="m",
            details=["a", "b"],
            fix="f",
        )
        assert len(c.details) == 2

    def test_extra_forbidden(self) -> None:
        """CheckResult rejects unknown fields."""
        with pytest.raises(ValidationError, match="extra"):
            CheckResult(
                name="x",
                category="y",
                passed=True,
                weight=1,
                message="m",
                details=[],
                fix="",
                typo_field="should fail",  # type: ignore[call-arg]
            )


# ─────────────────────────────────────────────────────────────────────────────
# CategoryScore
# ─────────────────────────────────────────────────────────────────────────────


class TestCategoryScore:
    """CategoryScore aggregates checks within a category."""

    def test_from_checks(self) -> None:
        checks = [
            CheckResult(
                name="a.1",
                category="a",
                passed=True,
                weight=5,
                message="ok",
                details=[],
                fix="",
            ),
            CheckResult(
                name="a.2",
                category="a",
                passed=False,
                weight=3,
                message="fail",
                details=["x"],
                fix="do y",
            ),
        ]
        cs = CategoryScore.from_checks("a", checks)
        assert cs.category == "a"
        assert cs.earned == 5
        assert cs.total == 8

    def test_all_passing(self) -> None:
        checks = [
            CheckResult(
                name="b.1",
                category="b",
                passed=True,
                weight=10,
                message="ok",
                details=[],
                fix="",
            ),
        ]
        cs = CategoryScore.from_checks("b", checks)
        assert cs.earned == cs.total == 10

    def test_extra_forbidden(self) -> None:
        """CategoryScore rejects unknown fields."""
        with pytest.raises(ValidationError, match="extra"):
            CategoryScore(
                category="a",
                earned=5,
                total=10,
                typo="bad",  # type: ignore[call-arg]
            )


# ─────────────────────────────────────────────────────────────────────────────
# ProjectResult
# ─────────────────────────────────────────────────────────────────────────────


class TestProjectResult:
    """ProjectResult computes score and grade from checks."""

    def _make_checks(self, pass_weight: int, fail_weight: int) -> list[CheckResult]:
        results = []
        if pass_weight > 0:
            results.append(
                CheckResult(
                    name="pass",
                    category="x",
                    passed=True,
                    weight=pass_weight,
                    message="ok",
                    details=[],
                    fix="",
                )
            )
        if fail_weight > 0:
            results.append(
                CheckResult(
                    name="fail",
                    category="x",
                    passed=False,
                    weight=fail_weight,
                    message="bad",
                    details=["x"],
                    fix="f",
                )
            )
        return results

    @pytest.mark.parametrize(
        ("pass_w", "fail_w", "expected_score", "expected_grade"),
        [
            pytest.param(100, 0, 100, Grade.A, id="perfect_score"),
            pytest.param(0, 100, 0, Grade.F, id="zero_score"),
            pytest.param(75, 25, 75, Grade.B, id="mixed_score"),
        ],
    )
    def test_score_and_grade(
        self,
        pass_w: int,
        fail_w: int,
        expected_score: int,
        expected_grade: Grade,
    ) -> None:
        r = ProjectResult.from_checks(Path("."), self._make_checks(pass_w, fail_w))
        assert r.score == expected_score
        assert r.grade == expected_grade

    def test_failures_list(self) -> None:
        r = ProjectResult.from_checks(Path("."), self._make_checks(80, 20))
        assert len(r.failures) == 1
        assert r.failures[0].name == "fail"

    def test_empty_checks_is_f(self) -> None:
        r = ProjectResult.from_checks(Path("."), [])
        assert r.score == 0
        assert r.grade == Grade.F

    def test_extra_forbidden(self) -> None:
        """ProjectResult rejects unknown fields."""
        with pytest.raises(ValidationError, match="extra"):
            ProjectResult(
                project_path=Path("."),
                checks=[],
                score=0,
                grade=Grade.F,
                categories={},
                failures=[],
                typo="bad",  # type: ignore[call-arg]
            )
