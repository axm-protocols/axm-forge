"""AXM Tool interface — structural protocol for deterministic tools.

Tools are the deterministic execution layer of the AXM architecture.
The LLM agent decides WHEN to invoke a tool (probabilistic decision),
but the tool itself executes deterministically.

Architecture:
    Agent (probabilistic) → orchestrator.run_tool() → AXMTool.execute() (deterministic)

Discovery:
    Tools are auto-discovered via entry points (group ``axm.tools``).
    Each tool defines its own ``execute()`` signature with explicit,
    typed parameters — the MCP discovery layer introspects these to
    generate JSON-Schema automatically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

__all__ = ["AXMTool", "ToolResult"]


@dataclass(frozen=True)
class ToolResult:
    """Immutable result of a tool execution.

    Attributes:
        success: Whether the tool execution succeeded.
        data: Structured output data (backend-specific).
        error: Human-readable error message, if any.
        hint: Optional next-step suggestion for the agent.
    """

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    hint: str | None = None


@runtime_checkable
class AXMTool(Protocol):
    """Structural protocol for AXM deterministic tools.

    Implementors must provide:
    - ``name`` (property): unique tool identifier
    - ``execute(...)`` : deterministic execution with explicit params

    Uses structural typing (PEP 544) — no inheritance required.
    ``@runtime_checkable`` enables ``isinstance()`` checks.

    Example::

        class MyTool:
            @property
            def name(self) -> str:
                return "my-tool"

            def execute(self, *, value: int = 0) -> ToolResult:
                return ToolResult(success=True, data={"result": value})
    """

    @property
    def name(self) -> str:
        """Unique tool identifier (e.g., 'esbmc', 'dafny', 'pytest')."""
        ...

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with given arguments.

        Subclasses should override with explicit, typed parameters::

            def execute(self, *, title: str = "", body: str = "") -> ToolResult:
                ...

        The ``**kwargs`` signature here is the *structural minimum* —
        any callable accepting keyword arguments satisfies it.

        Returns:
            ToolResult with success status and structured data.
        """
        ...
