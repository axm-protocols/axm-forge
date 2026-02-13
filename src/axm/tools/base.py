"""AXM Tool interface — base class for deterministic tools.

Tools are the deterministic execution layer of the AXM architecture.
The LLM agent decides WHEN to invoke a tool (probabilistic decision),
but the tool itself executes deterministically.

Architecture:
    Agent (probabilistic) → orchestrator.run_tool() → AXMTool.execute() (deterministic)

Discovery:
    Tools are auto-discovered via entry points (group ``axm.tools``).
    Install ``axm-formal`` to add verification tools (ESBMC, Dafny, Kind2).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

__all__ = ["AXMTool", "ToolResult"]


@dataclass(frozen=True)
class ToolResult:
    """Immutable result of a tool execution.

    Attributes:
        success: Whether the tool execution succeeded.
        data: Structured output data (backend-specific).
        error: Human-readable error message, if any.
    """

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class AXMTool(ABC):
    """Abstract base class for all AXM deterministic tools.

    Subclasses must implement:
    - ``name`` (property): unique tool identifier
    - ``execute(**kwargs)`` : deterministic execution

    Example::

        class MyTool(AXMTool):
            @property
            def name(self) -> str:
                return "my-tool"

            def execute(self, **kwargs: Any) -> ToolResult:
                return ToolResult(success=True, data={"result": 42})
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier (e.g., 'esbmc', 'dafny', 'pytest')."""

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with given arguments.

        Args:
            **kwargs: Tool-specific arguments.

        Returns:
            ToolResult with success status and structured data.
        """
