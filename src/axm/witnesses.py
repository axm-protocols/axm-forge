"""Base classes for witness validation.

WitnessResult represents validation outcomes.
ValidationFeedback provides structured error information.
WitnessRule is the Protocol for validation rules.

This module lives in ``axm`` (core) so that external packages
(axm-n8n, axm-mail, …) can implement witnesses without depending
on ``axm-engine``.  The engine re-exports these symbols from
``axm_engine.services.witnesses.base`` for backward compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

__all__ = [
    "ValidationFeedback",
    "WitnessResult",
    "WitnessRule",
]


@dataclass
class ValidationFeedback:
    """Structured feedback for validation failures.

    Attributes:
        what: What failed (brief description)
        why: Why it failed (expected vs actual)
        how: How to fix it (actionable guidance)
    """

    what: str
    why: str
    how: str

    def to_dict(self) -> dict[str, str]:
        """Serialize to dictionary."""
        return {"what": self.what, "why": self.why, "how": self.how}


@dataclass
class WitnessResult:
    """Result of a witness validation.

    Attributes:
        passed: Whether validation passed
        feedback: Feedback if validation failed
        verdict: Optional routing decision for Gates
        metadata: Optional execution metadata
    """

    passed: bool
    feedback: ValidationFeedback | None = None
    verdict: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(
        cls,
        verdict: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WitnessResult:
        """Create a passing result."""
        return cls(passed=True, verdict=verdict, metadata=metadata or {})

    @classmethod
    def failure(
        cls,
        feedback: ValidationFeedback,
        verdict: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WitnessResult:
        """Create a failing result with feedback."""
        return cls(
            passed=False, feedback=feedback, verdict=verdict, metadata=metadata or {}
        )


class WitnessRule(Protocol):
    """Protocol for witness validation rules."""

    def validate(self, content: str, **kwargs: Any) -> WitnessResult:
        """Validate content.

        Args:
            content: The content to validate
            **kwargs: Additional validation parameters

        Returns:
            WitnessResult indicating pass/fail with feedback
        """
        ...
