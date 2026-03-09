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

    def test_100_is_a(self) -> None:
        assert compute_grade(100) == Grade.A

    def test_90_is_a(self) -> None:
        assert compute_grade(90) == Grade.A

    def test_89_is_b(self) -> None:
        assert compute_grade(89) == Grade.B

    def test_75_is_b(self) -> None:
        assert compute_grade(75) == Grade.B

    def test_74_is_c(self) -> None:
        assert compute_grade(74) == Grade.C

    def test_60_is_c(self) -> None:
        assert compute_grade(60) == Grade.C

    def test_59_is_d(self) -> None:
        assert compute_grade(59) == Grade.D

    def test_40_is_d(self) -> None:
        assert compute_grade(40) == Grade.D

    def test_39_is_f(self) -> None:
        assert compute_grade(39) == Grade.F

    def test_0_is_f(self) -> None:
        assert compute_grade(0) == Grade.F


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

    def test_perfect_score(self) -> None:
        r = ProjectResult.from_checks(Path("."), self._make_checks(100, 0))
        assert r.score == 100
        assert r.grade == Grade.A

    def test_zero_score(self) -> None:
        r = ProjectResult.from_checks(Path("."), self._make_checks(0, 100))
        assert r.score == 0
        assert r.grade == Grade.F

    def test_mixed_score(self) -> None:
        r = ProjectResult.from_checks(Path("."), self._make_checks(75, 25))
        assert r.score == 75
        assert r.grade == Grade.B

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
