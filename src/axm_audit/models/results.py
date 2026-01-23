"""Result models for Agent-friendly JSON output."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, computed_field


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
    fix_hint: str | None = Field(default=None, description="Actionable fix suggestion")

    model_config = {"extra": "forbid"}


class AuditResult(BaseModel):
    """Aggregated result of a project audit.

    Contains all individual check results and computed summary.
    """

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
        """Weighted average of QUALITY_* rule scores.

        Weights: LINT=40%, TYPE=35%, COMPLEXITY=25%.
        Returns None if no quality checks are present.
        """
        weights = {
            "QUALITY_LINT": 0.40,
            "QUALITY_TYPE": 0.35,
            "QUALITY_COMPLEXITY": 0.25,
        }
        scores: dict[str, float] = {}
        for check in self.checks:
            if check.rule_id in weights and check.details:
                score = check.details.get("score")
                if score is not None:
                    scores[check.rule_id] = float(score)
        if not scores:
            return None
        return sum(scores.get(k, 0) * v for k, v in weights.items())

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
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"

    model_config = {"extra": "forbid"}


class ScaffoldResult(BaseModel):
    """Result of a project scaffolding operation."""

    success: bool = Field(..., description="Whether scaffolding succeeded")
    path: str = Field(..., description="Path to created project")
    message: str = Field(default="", description="Status message")
    files_created: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}
