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
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

__all__ = ["AXMTool", "ToolResult", "make_tool_class"]


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


def _to_class_name(tool_name: str) -> str:
    """Convert ``word_doc_create`` → ``WordDocCreate``."""
    return "".join(part.capitalize() for part in tool_name.split("_"))


def make_tool_class(
    tool_name: str,
    fn: Callable[..., dict[str, Any]],
) -> type[AXMTool]:
    """Return an :class:`AXMTool` subclass that wraps a plain function.

    Use this factory when you have many existing functions to expose as
    AXM tools without writing boilerplate subclasses for each one.  The
    returned class is instantiable (``cls()``), satisfies the
    ``ToolLike`` protocol, and can be registered as an ``axm.tools``
    entry point.

    Args:
        tool_name: MCP tool name (e.g. ``"word_doc_create"``).
        fn: Plain callable returning ``dict[str, Any]``.

    Returns:
        A new :class:`AXMTool` subclass whose ``execute(**kwargs)``
        delegates to *fn* and wraps the result in a :class:`ToolResult`.

    Example::

        from axm.tools.base import make_tool_class

        def my_fn(*, x: int) -> dict[str, Any]:
            return {"result": x * 2}

        MyTool = make_tool_class("my_tool", my_fn)
        assert MyTool().name == "my_tool"
        assert MyTool().execute(x=3).data == {"result": 6}
    """

    class _Tool(AXMTool):
        @property
        def name(self) -> str:
            """Return MCP tool name."""
            return tool_name

        def execute(self, **kwargs: Any) -> ToolResult:
            """Delegate to the wrapped function.

            Args:
                **kwargs: Forwarded to the underlying tool function.

            Returns:
                :class:`ToolResult` wrapping the function output or error.
            """
            try:
                data = fn(**kwargs)
                return ToolResult(success=True, data=data)
            except Exception as exc:
                return ToolResult(success=False, error=str(exc), data={})

    _Tool.__name__ = _to_class_name(tool_name)
    _Tool.__qualname__ = _to_class_name(tool_name)
    _Tool.__doc__ = fn.__doc__
    return _Tool
