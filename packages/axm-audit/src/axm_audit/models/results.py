"""Result models for Agent-friendly JSON output."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, PrivateAttr, computed_field

# ── Grade thresholds ──────────────────────────────────────────────────
_GRADE_A: int = 90
_GRADE_B: int = 80
_GRADE_C: int = 70
_GRADE_D: int = 60

# ── Quality-score category weights ───────────────────────────────────
_CATEGORY_WEIGHTS: dict[str, float] = {
    "lint": 0.20,
    "type": 0.15,
    "complexity": 0.15,
    "security": 0.10,
    "deps": 0.10,
    "testing": 0.15,
    "architecture": 0.10,
    "practices": 0.05,
}


def _collect_category_scores(
    checks: list[Any],
) -> dict[str, list[float]]:
    """Group valid scores by category, filtering out unusable checks."""
    category_scores: dict[str, list[float]] = {}
    for check in checks:
        cat = check.category
        if cat and cat in _CATEGORY_WEIGHTS and check.details:
            score = check.details.get("score")
            if score is not None:
                category_scores.setdefault(cat, []).append(float(score))
    return category_scores


class Severity(StrEnum):
    """Severity level for check results."""

    ERROR = "error"  # Blocks audit pass
    WARNING = "warning"  # Non-blocking issue
    INFO = "info"  # Informational only


class CheckResult(BaseModel):
    """Result of a single compliance check.

    Designed for machine parsing by AI Agents.
    """

    rule_id: str = Field(..., description="Unique identifier for the rule")
    passed: bool = Field(..., description="Whether the check passed")
    message: str = Field(..., description="Human-readable result message")
    severity: Severity = Field(default=Severity.ERROR, description="Severity level")
    details: dict[str, Any] | None = Field(
        default=None, description="Structured data (cycles, metrics)"
    )
    text: str | None = Field(
        default=None, description="Pre-rendered detail text for display"
    )
    fix_hint: str | None = Field(default=None, description="Actionable fix suggestion")
    category: str | None = Field(
        default=None, description="Scoring category (injected by auditor)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Rule-specific structured payload (clusters, verdicts, ...)",
    )

    model_config = {"extra": "forbid"}


class AuditResult(BaseModel):
    """Aggregated result of a project audit.

    Contains all individual check results and computed summary.
    ``quality_score`` and ``grade`` may be passed explicitly (e.g. in
    tests); otherwise they are computed from checks automatically.
    """

    project_path: str | None = Field(
        default=None, description="Path to the audited project"
    )
    checks: list[CheckResult] = Field(default_factory=list)

    _override_quality_score: float | None = PrivateAttr(default=None)
    _override_grade: str | None = PrivateAttr(default=None)

    def __init__(self, **data: Any) -> None:
        qs = data.pop("quality_score", None)
        gr = data.pop("grade", None)
        # Computed fields — silently dropped if passed (test convenience).
        for _computed in ("success", "total", "failed"):
            data.pop(_computed, None)
        super().__init__(**data)
        self._override_quality_score = qs
        self._override_grade = gr

    @computed_field  # type: ignore[prop-decorator]
    @property
    def success(self) -> bool:
        """True if all checks passed."""
        return all(c.passed for c in self.checks)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total(self) -> int:
        """Total number of checks."""
        return len(self.checks)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def failed(self) -> int:
        """Number of failed checks."""
        return sum(1 for c in self.checks if not c.passed)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def quality_score(self) -> float | None:
        """Weighted average across 8 code-quality categories.

        Categories and weights:
            Linting (20%), Type Safety (15%), Complexity (15%),
            Security (10%), Dependencies (10%), Testing (15%),
            Architecture (10%), Practices (5%).

        Structure is NOT scored here (handled by axm-init).
        Returns None if no scored checks are present.
        """
        override: float | None = getattr(self, "_override_quality_score", None)
        if override is not None:
            return override

        category_scores = _collect_category_scores(self.checks)
        if not category_scores:
            return None

        # Weighted average: avg each category, then weight.
        # Normalize by sum of present weights so filtered audits
        # (e.g. category="lint") are not penalized for missing categories.
        total = sum(
            (sum(scores) / len(scores)) * _CATEGORY_WEIGHTS[cat]
            for cat, scores in category_scores.items()
        )
        weight_sum = sum(_CATEGORY_WEIGHTS[cat] for cat in category_scores)
        if weight_sum <= 0:
            return None
        return round(total / weight_sum, 1)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def grade(self) -> str | None:
        """Letter grade derived from quality_score.

        A >= 90, B >= 80, C >= 70, D >= 60, F < 60.
        Returns None if quality_score is None.
        """
        override: str | None = getattr(self, "_override_grade", None)
        if override is not None:
            return override

        score = self.quality_score
        if score is None:
            return None
        _thresholds = [
            (_GRADE_A, "A"),
            (_GRADE_B, "B"),
            (_GRADE_C, "C"),
            (_GRADE_D, "D"),
        ]
        return next((g for t, g in _thresholds if score >= t), "F")

    model_config = {"extra": "forbid"}
