"""Base classes for hook execution.

HookResult represents hook execution outcomes.
HookAction defines the protocol for hook implementations.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol

__all__ = ["HookAction", "HookResult"]


@dataclass
class HookResult:
    """Result of a hook execution.

    Attributes:
        success: Whether the hook succeeded
        error: Error message if failed
        metadata: Optional execution metadata
    """

    success: bool
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, **metadata: Any) -> "HookResult":
        """Create a successful result."""
        return cls(success=True, metadata=metadata)

    @classmethod
    def fail(cls, error: str, **metadata: Any) -> "HookResult":
        """Create a failed result."""
        return cls(success=False, error=error, metadata=metadata)


class HookAction(Protocol):
    """Protocol for hook implementations.

    All hook actions receive a context dict with session info:
    - session_id: str
    - protocol_name: str
    - phase_name: str
    - task_name: str | None
    - working_dir: str | None
    - artifacts_path: str | None
    """

    def execute(self, context: dict[str, Any], **params: Any) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary
            **params: Hook-specific parameters

        Returns:
            HookResult indicating success/failure with metadata
        """
        ...
