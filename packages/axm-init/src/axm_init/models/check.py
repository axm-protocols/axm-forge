"""Check models — Grade, CheckResult, ProjectResult, CategoryScore."""

from __future__ import annotations

__all__ = ["CategoryScore", "CheckResult", "Grade", "ProjectResult", "compute_grade"]

import logging
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, computed_field

logger = logging.getLogger(__name__)


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


class CheckResult(BaseModel):  # type: ignore[explicit-any]
    """Result of a single audit check.

    Note: ``type: ignore[explicit-any]`` flags pydantic ``BaseModel``
    internals (third-party).
    """

    model_config = ConfigDict(extra="forbid")

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


class CategoryScore(BaseModel):  # type: ignore[explicit-any]
    """Aggregated score verdict for a category.

    When the summed weight of applicable checks is 0 the category is
    *not applicable* (N/A): :attr:`applicable` is ``False`` and both
    :attr:`score` and :attr:`grade` are ``None`` — a distinct status, not a
    numeric 0/100. An applicable category where every check fails still
    scores a real ``0`` / Grade ``F`` (:attr:`applicable` stays ``True``).

    Note: ``type: ignore[explicit-any]`` flags pydantic ``BaseModel``
    internals (third-party).
    """

    model_config = ConfigDict(extra="forbid")

    category: str
    earned: int
    total: int

    @computed_field  # type: ignore[prop-decorator]
    @property
    def applicable(self) -> bool:
        """Whether any applicable checks ran (summed weight > 0).

        ``False`` marks a not-applicable (N/A) verdict: the category had no
        weighted checks to score, which is distinct from a real 0/100.
        """
        return self.total > 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def not_applicable(self) -> bool:
        """Inverse of :attr:`applicable` — True when no weighted checks ran."""
        return not self.applicable

    @computed_field  # type: ignore[prop-decorator]
    @property
    def score(self) -> int | None:
        """0-100 weighted score, or ``None`` when not applicable.

        ``None`` (never a numeric 0) is the N/A signal; an applicable
        category where every check fails still scores a real ``0``.
        """
        if not self.applicable:
            return None
        return round(self.earned / self.total * 100)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def grade(self) -> Grade | None:
        """Letter grade, or ``None`` when not applicable (no numeric grade)."""
        current = self.score
        return compute_grade(current) if current is not None else None

    @classmethod
    def from_checks(cls, category: str, checks: list[CheckResult]) -> CategoryScore:
        """Build the category verdict from its checks.

        Sums the weighted results; the applicability/N/A status and the
        derived score/grade fall out of :attr:`total` (0 → N/A).
        """
        return cls(
            category=category,
            earned=sum(c.earned for c in checks),
            total=sum(c.weight for c in checks),
        )


def _compute_score(checks: list[CheckResult]) -> int:
    """Compute weighted percentage score from check results."""
    total_weight = sum(c.weight for c in checks)
    total_earned = sum(c.earned for c in checks)
    return round(total_earned / total_weight * 100) if total_weight > 0 else 0


def _group_categories(checks: list[CheckResult]) -> dict[str, CategoryScore]:
    """Group checks by category and compute per-category scores."""
    cat_map: dict[str, list[CheckResult]] = {}
    for c in checks:
        cat_map.setdefault(c.category, []).append(c)
    return {
        cat: CategoryScore.from_checks(cat, cat_checks)
        for cat, cat_checks in cat_map.items()
    }


class ProjectResult(BaseModel):  # type: ignore[explicit-any]
    """Complete project check result with score and grade.

    Note: ``type: ignore[explicit-any]`` flags pydantic ``BaseModel``
    internals (third-party).
    """

    model_config = ConfigDict(extra="forbid")

    project_path: Path
    checks: list[CheckResult]
    score: int
    grade: Grade
    categories: dict[str, CategoryScore]
    failures: list[CheckResult]
    context: str | None = None
    workspace_root: Path | None = None
    excluded_checks: list[str] = []

    @property
    def applicable(self) -> bool:
        """Whether any weighted check ran (summed check weight > 0).

        ``False`` is a not-applicable (N/A) verdict for the whole run — e.g.
        ``check --category workspace`` on a standalone project skips every
        workspace check, leaving nothing to score. Distinct from a real
        0/100 where checks ran but all failed.
        """
        return any(c.weight > 0 for c in self.checks)

    @property
    def not_applicable(self) -> bool:
        """Inverse of :attr:`applicable` — True when no weighted checks ran."""
        return not self.applicable

    @classmethod
    def from_checks(
        cls,
        project_path: Path,
        checks: list[CheckResult],
        *,
        context: str | None = None,
        workspace_root: Path | None = None,
        excluded_checks: list[str] | None = None,
    ) -> ProjectResult:
        """Compute score, grade, and category breakdowns from check results."""
        score = _compute_score(checks)
        categories = _group_categories(checks)
        failures = [c for c in checks if not c.passed]

        return cls(
            project_path=project_path,
            checks=checks,
            score=score,
            grade=compute_grade(score),
            categories=categories,
            failures=failures,
            context=context,
            workspace_root=workspace_root,
            excluded_checks=excluded_checks or [],
        )
