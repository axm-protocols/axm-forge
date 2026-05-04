"""Result models for Agent-friendly JSON output."""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, computed_field

_logger = logging.getLogger(__name__)

# ── Grade thresholds ──────────────────────────────────────────────────
_GRADE_A: int = 90
_GRADE_B: int = 80
_GRADE_C: int = 70
_GRADE_D: int = 60

# ── Quality-score category weights ───────────────────────────────────
# Sum must equal 1.0. Categories absent here (structure, tooling) emit
# findings but are NOT scored. Adding a category requires updating
# docs/explanation/scoring.md and the ASCII table in core/rules/base.py.
_CATEGORY_WEIGHTS: dict[str, float] = {
    "lint": 0.15,
    "type": 0.15,
    "complexity": 0.15,
    "security": 0.10,
    "deps": 0.10,
    "testing": 0.10,
    "test_quality": 0.10,
    "architecture": 0.10,
    "practices": 0.05,
}

# Public views over the private weights table. ``SCORED_CATEGORIES`` is the
# canonical set of categories that contribute to ``quality_score``;
# ``EXTRA_NONSCORED_CATEGORIES`` lists categories that emit findings but are
# not scored (see scoring docstring on ``AuditResult.quality_score``).
SCORED_CATEGORIES: frozenset[str] = frozenset(_CATEGORY_WEIGHTS)
EXTRA_NONSCORED_CATEGORIES: frozenset[str] = frozenset({"structure", "tooling"})


def _collect_category_scores(
    checks: list[Any],
) -> dict[str, list[float]]:
    """Group valid scores by category, filtering out unusable checks.

    Reads the typed ``CheckResult.score`` field. When a check belongs to a
    scored category but exposes ``score is None``, a warning is emitted naming
    the rule_id so that silently-dropped scores remain observable.
    """
    category_scores: dict[str, list[float]] = {}
    for check in checks:
        cat = check.category
        if not cat or cat not in _CATEGORY_WEIGHTS:
            continue
        if check.score is None:
            _logger.warning(
                "rule %s in scored category %r returned score=None; dropped",
                check.rule_id,
                cat,
            )
            continue
        category_scores.setdefault(cat, []).append(float(check.score))
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
    score: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Numeric score in [0, 100] for scored categories",
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
        """Weighted average across 9 code-quality categories.

        Categories and weights:
            Linting (15%), Type Safety (15%), Complexity (15%),
            Testing (10%), Test Quality (10%), Security (10%),
            Dependencies (10%), Architecture (10%), Practices (5%).

        Structure and tooling emit findings but are NOT scored
        (structure is handled by axm-init; tooling is informational).
        Returns None if no scored checks are present.
        """
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
