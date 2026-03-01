"""Result models for Agent-friendly JSON output."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, computed_field

# ── Grade thresholds ──────────────────────────────────────────────────
_GRADE_A: int = 90
_GRADE_B: int = 80
_GRADE_C: int = 70
_GRADE_D: int = 60


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
        """Weighted average across 8 code-quality categories.

        Categories and weights:
            Linting (20%), Type Safety (15%), Complexity (15%),
            Security (10%), Dependencies (10%), Testing (15%),
            Architecture (10%), Practices (5%).

        Structure is NOT scored here (handled by axm-init).
        Returns None if no scored checks are present.
        """
        category_weights = {
            "lint": 0.20,
            "type": 0.15,
            "complexity": 0.15,
            "security": 0.10,
            "deps": 0.10,
            "testing": 0.15,
            "architecture": 0.10,
            "practices": 0.05,
        }

        # Map rule_id prefixes to categories
        rule_to_category: dict[str, str] = {
            "QUALITY_LINT": "lint",
            "QUALITY_FORMAT": "lint",
            "QUALITY_DIFF_SIZE": "lint",
            "QUALITY_DEAD_CODE": "lint",
            "QUALITY_TYPE": "type",
            "QUALITY_COMPLEXITY": "complexity",
            "QUALITY_SECURITY": "security",
            "DEPS_AUDIT": "deps",
            "DEPS_HYGIENE": "deps",
            "QUALITY_COVERAGE": "testing",
            "ARCH_COUPLING": "architecture",
            "ARCH_CIRCULAR": "architecture",
            "ARCH_GOD_CLASS": "architecture",
            "ARCH_DUPLICATION": "architecture",
            "PRACTICE_DOCSTRING": "practices",
            "PRACTICE_BARE_EXCEPT": "practices",
            "PRACTICE_SECURITY": "practices",
            "PRACTICE_BLOCKING_IO": "practices",
            "PRACTICE_LOGGING": "practices",
            "PRACTICE_TEST_MIRROR": "practices",
        }

        # Collect scores by category
        category_scores: dict[str, list[float]] = {}
        for check in self.checks:
            cat = rule_to_category.get(check.rule_id)
            if cat and check.details:
                score = check.details.get("score")
                if score is not None:
                    category_scores.setdefault(cat, []).append(float(score))

        if not category_scores:
            return None

        # Weighted average: avg each category, then weight
        total = 0.0
        for cat, weight in category_weights.items():
            scores = category_scores.get(cat, [])
            if scores:
                total += (sum(scores) / len(scores)) * weight
            # Missing categories contribute 0

        return round(total, 1)

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
        if score >= _GRADE_A:
            return "A"
        if score >= _GRADE_B:
            return "B"
        if score >= _GRADE_C:
            return "C"
        if score >= _GRADE_D:
            return "D"
        return "F"

    model_config = {"extra": "forbid"}
