"""Check models — Grade, CheckResult, ProjectResult, CategoryScore."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, computed_field


class Grade(StrEnum):
    """AXM gold standard grade."""

    A = "A"  # ≥90
    B = "B"  # ≥75
    C = "C"  # ≥60
    D = "D"  # ≥40
    F = "F"  # <40


def compute_grade(score: int | float) -> Grade:
    """Map a 0-100 score to a Grade."""
    if score >= 90:
        return Grade.A
    if score >= 75:
        return Grade.B
    if score >= 60:
        return Grade.C
    if score >= 40:
        return Grade.D
    return Grade.F


class CheckResult(BaseModel):
    """Result of a single audit check."""

    name: str
    category: str
    passed: bool
    weight: int
    message: str
    details: list[str]
    fix: str

    @computed_field  # type: ignore[prop-decorator]
    @property
    def earned(self) -> int:
        """Points earned: weight if passed, 0 otherwise."""
        return self.weight if self.passed else 0


class CategoryScore(BaseModel):
    """Aggregated score for a category."""

    category: str
    earned: int
    total: int

    @classmethod
    def from_checks(cls, category: str, checks: list[CheckResult]) -> CategoryScore:
        """Build from a list of checks belonging to this category."""
        return cls(
            category=category,
            earned=sum(c.earned for c in checks),
            total=sum(c.weight for c in checks),
        )


class ProjectResult(BaseModel):
    """Complete project check result with score and grade."""

    project_path: Path
    checks: list[CheckResult]
    score: int
    grade: Grade
    categories: dict[str, CategoryScore]
    failures: list[CheckResult]

    @classmethod
    def from_checks(
        cls, project_path: Path, checks: list[CheckResult]
    ) -> ProjectResult:
        """Compute score, grade, and category breakdowns from check results."""
        total_weight = sum(c.weight for c in checks)
        total_earned = sum(c.earned for c in checks)
        score = round(total_earned / total_weight * 100) if total_weight > 0 else 0

        # Group by category
        cat_map: dict[str, list[CheckResult]] = {}
        for c in checks:
            cat_map.setdefault(c.category, []).append(c)

        categories = {
            cat: CategoryScore.from_checks(cat, cat_checks)
            for cat, cat_checks in cat_map.items()
        }

        failures = [c for c in checks if not c.passed]

        return cls(
            project_path=project_path,
            checks=checks,
            score=score,
            grade=compute_grade(score),
            categories=categories,
            failures=failures,
        )
