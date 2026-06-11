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

__all__ = ["AXMTool", "ToolMetadata", "ToolResult", "tool_metadata"]


@dataclass(frozen=True)
class ToolResult:
    """Immutable result of a tool execution.

    Attributes:
        success: Whether the tool execution succeeded.
        data: Structured output data (backend-specific).
        error: Human-readable error message, if any.
        hint: Optional next-step suggestion for the agent.
        text: Optional pre-rendered text representation (e.g. Markdown).
    """

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    hint: str | None = None
    text: str | None = None


@runtime_checkable
class AXMTool(Protocol):
    """Structural protocol for AXM deterministic tools.

    Implementors must provide:
    - ``name`` (property): unique tool identifier
    - ``execute(...)`` : deterministic execution with explicit params

    Optionally provide:
    - ``agent_hint`` (class attribute): optional, free-form one-liner
      optimized for LLM consumption: what the tool does, key params, and
      what it replaces.  Like the other discovery attributes below, it is
      *not* a protocol member and carries no guaranteed fallback — some
      discovery tooling reads it best-effort via ``getattr`` /
      :func:`tool_metadata`; absent, nothing is substituted.
    - ``expose_directly`` (class attribute, default ``False``): when
      ``True``, the MCP server registers this tool directly in
      ``tools/list`` (the *hot path*).  When ``False`` (default), the
      tool is reachable only through the MCP facade
      (``axm_search`` -> ``axm_describe`` -> ``axm_call``), keeping the
      ``tools/list`` payload small.
    - ``domain`` (class attribute, default ``None``): coarse capability
      group used by the facade for ``axm_capabilities`` and to scope
      ``axm_search`` (e.g. ``"ast"``, ``"git"``, ``"ticket"``).
    - ``tags`` (class attribute, default ``frozenset()``): free-form
      keywords feeding facade discovery (``axm_search``).

    Uses structural typing (PEP 544) — no inheritance required.
    ``@runtime_checkable`` enables ``isinstance()`` checks.  The discovery
    attributes (``expose_directly`` / ``domain`` / ``tags``) are *not*
    protocol members on purpose: adding data attributes to a
    ``runtime_checkable`` protocol would make them required for
    ``isinstance()`` and break the check for the many tools that satisfy
    ``AXMTool`` structurally without subclassing it.  Read them through
    :func:`tool_metadata` (or ``getattr(tool, name, default)``) instead,
    which works for subclasses and structural tools alike.

    Example::

        class MyTool(AXMTool):
            agent_hint = "Frobnicate widgets — use width param."
            expose_directly = True          # hot path (read via tool_metadata)
            domain = "widget"
            tags = frozenset({"frobnicate"})

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


@dataclass(frozen=True)
class ToolMetadata:
    """Facade/CLI discovery metadata for a tool, with safe defaults.

    Built by :func:`tool_metadata` from the optional ``expose_directly`` /
    ``domain`` / ``tags`` attributes a tool may declare.  Centralising the
    defaults here keeps the MCP facade and the CLI reading the same contract.

    Attributes:
        expose_directly: Whether the tool is on the MCP hot path
            (registered directly in ``tools/list``).  Default ``False``.
        domain: Coarse capability group, or ``None`` if ungrouped.
        tags: Discovery keywords (possibly empty).
    """

    expose_directly: bool = False
    domain: str | None = None
    tags: frozenset[str] = frozenset()


def tool_metadata(tool: object) -> ToolMetadata:
    """Read a tool's optional discovery attributes into a :class:`ToolMetadata`.

    Works for tools that subclass :class:`AXMTool`, tools that satisfy it
    structurally, and plain callables — anything missing an attribute falls
    back to the default.  ``tags`` is coerced to a ``frozenset`` so callers
    can rely on set semantics regardless of how the tool declared it.

    Args:
        tool: The tool instance (or plain callable) to introspect.

    Returns:
        A :class:`ToolMetadata` with resolved values.
    """
    raw_tags = getattr(tool, "tags", None) or ()
    return ToolMetadata(
        expose_directly=bool(getattr(tool, "expose_directly", False)),
        domain=getattr(tool, "domain", None),
        tags=frozenset(raw_tags),
    )
