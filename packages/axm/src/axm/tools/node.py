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
  ``if_``) so the tool is only invoked when it can succeed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from axm.tools._discovery import entry_points_for

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from axm.tools.base import AXMTool

__all__ = ["TOOLS_ENTRY_POINT_GROUP", "ToolNodeError", "tool_node"]

#: The entry-point group tools are discovered under (one declaration, three uses).
TOOLS_ENTRY_POINT_GROUP = "axm.tools"

#: Sentinel mapping a write key to the tool's ``ToolResult.text``.
_TEXT = "text"


class ToolNodeError(RuntimeError):
    """A tool invoked as a DAG node failed (``ToolResult.success`` was ``False``)."""


def _load_tool(name: str) -> AXMTool:
    """Resolve and instantiate the ``axm.tools`` entry point named *name*."""
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

    Returns:
        A callable mapping the node's ``payload`` to a dict keyed by *returns*.

    Raises:
        ToolNodeError: At call time, if the tool is unknown or returns
            ``success=False`` (fail-fast).
    """
    rename = dict(args or {})
    out_spec = dict(returns or {})

    def _run(payload: Mapping[str, object]) -> dict[str, object]:
        tool = _load_tool(name)
        kwargs = _kwargs_from_payload(payload, rename)
        try:
            result = tool.execute(**kwargs)
        except TypeError as exc:
            # A payload key with no matching ``execute`` parameter (strict
            # signature, no ``**kwargs``) must surface as the documented
            # ToolNodeError, not a raw TypeError.
            msg = f"tool {name!r}: bad payload for execute(): {exc}"
            raise ToolNodeError(msg) from exc
        if not result.success:
            msg = f"tool {name!r} failed: {result.error or '<no error message>'}"
            raise ToolNodeError(msg)
        return _shape_output(name, result.data, result.text, out_spec)

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
