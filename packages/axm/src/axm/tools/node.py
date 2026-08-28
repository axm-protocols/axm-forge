"""Adapt an :class:`~axm.tools.base.AXMTool` into a DAG python-node function.

This is the third consumer of the single ``axm.tools`` declaration: the same
tool that MCP exposes and the CLI auto-generates can be called *directly from a
DAG node*, with no ``HookAction`` and no subprocess. One entry point → MCP + CLI
+ node (see ``synchronisation_cmp_cli/README.md``, révision axm-dag).

A DAG python node is a callable ``fn(payload) -> dict`` whose returned keys are
the node's ``writes``. :func:`tool_node` builds such a callable around a tool:

* **inputs** — the node's ``reads`` arrive in ``payload``; they map to the tool's
  ``execute(**kwargs)`` by name, or via an explicit ``args`` rename map when the
  mem key differs from the parameter name;
* **outputs** — ``returns`` maps each write key to its source: the literal
  ``"text"`` (the tool's ``ToolResult.text``) or a key inside ``ToolResult.data``;
* **failure** — fail-fast: a tool returning ``success=False`` raises
  :class:`ToolNodeError`. Guard preconditions with a conditional node (router /
  ``if_``) so the tool is only invoked when it can succeed;
* **substitution** — :func:`override_tools` swaps named tools for the dynamic
  extent of a block (a :mod:`contextvars` scope, so it follows ``asyncio`` tasks
  and ``asyncio.to_thread`` — the paths a DAG run executes nodes on). It is the
  tool-side twin of an injected agent backend: a graph's *logic* can run against
  in-memory fakes of ``audit_test``/``git_*``/… without forking the real
  toolchain, while the node's own payload/output shaping stays exercised.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

from axm.tools._discovery import entry_points_for

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping

    from axm.tools.base import AXMTool

__all__ = ["TOOLS_ENTRY_POINT_GROUP", "ToolNodeError", "override_tools", "tool_node"]

#: Active tool substitutions (``override_tools``), scoped by contextvars so a
#: substitution installed by a test body is seen by the tasks/threads the DAG
#: scheduler spawns from it — and by nothing outside that dynamic extent.
_OVERRIDES: ContextVar[Mapping[str, AXMTool] | None] = ContextVar(
    "axm_tool_overrides", default=None
)

#: The entry-point group tools are discovered under (one declaration, three uses).
TOOLS_ENTRY_POINT_GROUP = "axm.tools"

#: Sentinel mapping a write key to the tool's ``ToolResult.text``.
_TEXT = "text"


class ToolNodeError(RuntimeError):
    """A tool invoked as a DAG node failed (``ToolResult.success`` was ``False``)."""


@contextmanager
def override_tools(tools: Mapping[str, AXMTool]) -> Iterator[None]:
    """Substitute *tools* (``{entry_point_name: tool}``) for the duration of a block.

    Inside the block, a :func:`tool_node` built for one of the named tools calls
    the substitute instead of resolving the ``axm.tools`` entry point — whether
    the node was built before or after entering the block, and whether or not
    the real tool had already been resolved and memoized. Blocks nest: an inner
    block adds to (or shadows, per name) the enclosing one, and leaving it
    restores exactly what was active before.

    The substitution applies to every resolution *by name* — :func:`tool_node`
    nodes and direct :func:`_load_tool` callers alike — so a graph node that
    resolves a tool itself (``_load_tool("echo_check")`` in a python node) is
    covered too, not only ``tool_node`` wrappers.

    The scope is a :mod:`contextvars` context, not a global: it propagates to
    ``asyncio`` tasks and :func:`asyncio.to_thread` calls started inside the
    block (how ``axm_dag`` executes python nodes) and is invisible to concurrent
    work started outside it. Substitutes are never memoized, so the real tool
    resolves again as soon as the block exits.

    Args:
        tools: Entry-point name → substitute implementing ``execute(**kwargs)
            -> ToolResult``.
    """
    active = _OVERRIDES.get() or {}
    token = _OVERRIDES.set({**active, **tools})
    try:
        yield
    finally:
        _OVERRIDES.reset(token)


def _load_tool(name: str) -> AXMTool:
    """Resolve and instantiate the ``axm.tools`` entry point named *name*."""
    # An active ``override_tools`` substitute wins over discovery, for direct
    # callers as well as for ``tool_node`` (which consults it before its cache).
    overrides = _OVERRIDES.get()
    if overrides and name in overrides:
        return overrides[name]
    eps = entry_points_for(TOOLS_ENTRY_POINT_GROUP)
    ep = eps.get(name)
    if ep is not None:
        obj = ep.load()
        tool: AXMTool = obj() if isinstance(obj, type) else obj
        return tool
    known = ", ".join(sorted(eps))
    msg = f"No tool registered under {name!r}. Registered: {known or '<none>'}"
    raise ToolNodeError(msg)


def tool_node(
    name: str,
    *,
    args: Mapping[str, str] | None = None,
    returns: Mapping[str, str] | None = None,
    allow_failure_data: bool = False,
) -> Callable[[Mapping[str, object]], dict[str, object]]:
    """Build a DAG python-node ``fn(payload) -> dict`` around an ``axm.tools`` tool.

    Args:
        name: The tool's ``axm.tools`` entry-point name (e.g. ``"ast_impact"``).
        args: Optional ``{param_name: mem_key}`` rename map for params whose mem
            key differs from the ``execute`` parameter name. Params absent from
            *args* are read from ``payload`` by their own name when present.
        returns: ``{write_key: source}`` where *source* is ``"text"`` (the
            ``ToolResult.text``) or a key inside ``ToolResult.data``. Defaults to
            ``{name: "text"}`` is **not** assumed — supply it so the node's writes
            are explicit (decision: writes nommés par clé).

            Precedence / collision: the literal ``"text"`` is a sentinel that
            **always** routes to ``ToolResult.text``, checked *before* any lookup
            in ``ToolResult.data``. A tool whose ``data`` carries its own
            ``"text"`` key therefore cannot surface that field through this
            shortcut — ``source="text"`` yields ``ToolResult.text``, never
            ``data["text"]`` (which is unreachable via *returns*). Route such a
            field under a different write source, or rename the data key upstream.
        allow_failure_data: Opt-in for observation tools whose ``success=False``
            is itself measured domain data (for example ``audit_test`` returning
            exact failed cases).  When true, shape ``ToolResult.data`` through
            *returns* instead of raising solely on the success flag. Missing
            declared data still raises, so an empty/tool failure cannot become
            evidence. Defaults to the existing fail-fast behaviour.

    Returns:
        A callable mapping the node's ``payload`` to a dict keyed by *returns*.

    Raises:
        ToolNodeError: At call time, if the tool is unknown, returns
            ``success=False`` without the explicit observation opt-in, or omits
            one of the declared return fields.
    """
    rename = dict(args or {})
    out_spec = dict(returns or {})
    cache: dict[str, AXMTool] = {}

    def _run(payload: Mapping[str, object]) -> dict[str, object]:
        overrides = _OVERRIDES.get()
        if overrides and name in overrides:
            # A substitute shadows even a memoized real tool and never enters
            # the cache: it lives exactly as long as its block.
            tool: AXMTool = overrides[name]
        else:
            cached = cache.get(name)
            if cached is None:
                # Resolve entry points + instantiate once, lazily on first call
                # (late-binding): building the node scans nothing.
                cached = _load_tool(name)
                cache[name] = cached
            tool = cached
        kwargs = _kwargs_from_payload(payload, rename)
        try:
            result = tool.execute(**kwargs)
        except TypeError as exc:
            # A payload key with no matching ``execute`` parameter (strict
            # signature, no ``**kwargs``) must surface as the documented
            # ToolNodeError, not a raw TypeError.
            msg = f"tool {name!r}: bad payload for execute(): {exc}"
            raise ToolNodeError(msg) from exc
        if not result.success and not allow_failure_data:
            msg = f"tool {name!r} failed: {result.error or '<no error message>'}"
            raise ToolNodeError(msg)
        try:
            return _shape_output(name, result.data, result.text, out_spec)
        except ToolNodeError as exc:
            if not result.success and result.error:
                msg = f"tool {name!r} failed: {result.error}; {exc}"
                raise ToolNodeError(msg) from exc
            raise

    return _run


def _kwargs_from_payload(
    payload: Mapping[str, object],
    rename: Mapping[str, str],
) -> dict[str, object]:
    """Map the node payload to ``execute`` kwargs (rename map > same-name key)."""
    kwargs: dict[str, object] = {}
    for param, mem_key in rename.items():
        if mem_key in payload:
            kwargs[param] = payload[mem_key]
    for key, value in payload.items():
        if key not in rename.values() and key not in kwargs:
            kwargs[key] = value
    return kwargs


def _shape_output(
    name: str,
    data: Mapping[str, object],
    text: str | None,
    out_spec: Mapping[str, str],
) -> dict[str, object]:
    """Build the write dict from the spec: ``"text"`` → text, else a data key."""
    out: dict[str, object] = {}
    for write_key, source in out_spec.items():
        if source == _TEXT:
            out[write_key] = text
        elif source in data:
            out[write_key] = data[source]
        else:
            msg = f"tool {name!r}: no {source!r} in result.data for write {write_key!r}"
            raise ToolNodeError(msg)
    return out
