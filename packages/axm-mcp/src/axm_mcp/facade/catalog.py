"""In-memory catalog backing the four MCP facade meta-tools.

``ToolCatalog`` wraps the ``discover_tools()`` dict and provides the four
operations the facade exposes:

* :meth:`search` — keyword/tag lookup over name + summary + tags + domain;
* :meth:`describe` — the full invocation contract (typed params + docstring);
* :meth:`call` — execute a tool by name and return its ``ToolResult.text``
  (falling back to the flattened ``data`` dict when there is no text);
* :meth:`capabilities` — compact per-domain grouping.

Discovery metadata (``expose_directly`` / ``domain`` / ``tags``) is read via
:func:`axm.tools.base.tool_metadata`, so both ``AXMTool`` subclasses and
structural tools work unchanged.  Typed parameters reuse
:func:`axm_mcp.schema.signature_params` — the exact introspection FastMCP
itself uses — so ``axm_describe`` and the per-tool MCP schema agree.
"""

from __future__ import annotations

import dataclasses
import inspect
from typing import TYPE_CHECKING, cast

from axm.tools.base import tool_metadata

from axm_mcp.schema import IntrospectableFn, signature_params
from axm_mcp.wrapping import build_wrappers

if TYPE_CHECKING:
    from axm_mcp.discovery import ToolEntry
    from axm_mcp.wrapping import _AnyWrapper, _SyncWrapper

__all__ = ["ToolCatalog", "UnknownToolError"]


@dataclasses.dataclass(frozen=True)
class _ParamSpec:
    """One parameter of a tool's invocation contract."""

    name: str
    annotation: str
    required: bool
    default: str | None


#: Default cap on ``search`` results.
_DEFAULT_LIMIT = 20

#: First-line length cap for summaries.
_SUMMARY_LEN = 120


class UnknownToolError(KeyError):
    """Raised when a tool name is not present in the catalog."""


def _exec_fn(tool: ToolEntry) -> IntrospectableFn:
    """Return the introspectable callable for a tool entry.

    Plain dispatcher tools are callables themselves; ``AXMTool`` instances
    expose their logic via ``.execute``.
    """
    execute = getattr(tool, "execute", None)
    return cast(IntrospectableFn, execute if execute is not None else tool)


def _doc(tool: ToolEntry) -> str:
    """Full docstring of a tool's executable, or empty string."""
    return inspect.getdoc(_exec_fn(tool)) or ""


def _summary(tool: ToolEntry) -> str:
    """First non-empty docstring line, truncated for listing."""
    for line in _doc(tool).splitlines():
        line = line.strip()
        if line:
            return line[:_SUMMARY_LEN]
    return ""


class ToolCatalog:
    """Searchable index over discovered ``axm.tools`` entries.

    Args:
        tools: The ``discover_tools()`` mapping (name -> tool entry).  The
            catalog stores it by reference; it does not re-discover.
    """

    def __init__(self, tools: dict[str, ToolEntry]) -> None:
        self._entries = tools
        # Build the SAME wrapper pair the direct MCP path uses, so
        # ``axm_call`` runs through the identical lock/trace/flatten contract
        # (there is a single execution path). Built lazily-eager here so
        # discovery cost is paid once, at catalog construction.
        self._wrappers: dict[str, tuple[_SyncWrapper, _AnyWrapper]] = {
            name: build_wrappers(name, tool) for name, tool in tools.items()
        }

    # ── introspection ────────────────────────────────────────────────────

    def names(self) -> list[str]:
        """All tool names, sorted."""
        return sorted(self._entries)

    def hot_path(self) -> list[str]:
        """Names of tools opting into direct MCP exposure (``expose_directly``)."""
        return sorted(
            name
            for name, tool in self._entries.items()
            if tool_metadata(tool).expose_directly
        )

    # ── facade operations ────────────────────────────────────────────────

    def search(
        self,
        query: str,
        domain: str | None = None,
        limit: int = _DEFAULT_LIMIT,
    ) -> list[dict[str, object]]:
        """Find tools whose name, summary, tags or domain match *query*.

        Matching is case-insensitive substring (the deliberately-simple v1;
        tags carry discovery quality).  An empty *query* lists everything
        (optionally scoped by *domain*), which makes the facade browsable.

        Args:
            query: Substring to look for. Empty matches all.
            domain: Optional exact-match domain filter.
            limit: Maximum number of results.

        Returns:
            A list of ``{name, summary, domain, tags}`` dicts, name-sorted.
        """
        q = query.lower().strip()
        results: list[dict[str, object]] = []
        for name in sorted(self._entries):
            tool = self._entries[name]
            meta = tool_metadata(tool)
            if domain is not None and meta.domain != domain:
                continue
            summary = _summary(tool)
            haystack = f"{name}\n{summary}\n{' '.join(meta.tags)}\n{meta.domain or ''}"
            if q and q not in haystack.lower():
                continue
            results.append(
                {
                    "name": name,
                    "summary": summary,
                    "domain": meta.domain,
                    "tags": sorted(meta.tags),
                }
            )
            if len(results) >= limit:
                break
        return results

    def describe(self, name: str) -> dict[str, object]:
        """Return the full invocation contract for *name*.

        Args:
            name: Tool name.

        Returns:
            ``{name, summary, domain, tags, docstring, params}`` where each
            param is ``{name, annotation, required, default}``.

        Raises:
            UnknownToolError: If *name* is not in the catalog.
        """
        tool = self._get(name)
        meta = tool_metadata(tool)
        return {
            "name": name,
            "summary": _summary(tool),
            "domain": meta.domain,
            "tags": sorted(meta.tags),
            "docstring": _doc(tool),
            "params": [dataclasses.asdict(p) for p in self._params(name)],
        }

    def call(self, name: str, arguments: dict[str, object] | None = None) -> str:
        """Execute *name* synchronously and return its text output.

        Delegates to the *same* sync wrapper the direct MCP path registers
        (built by :func:`axm_mcp.wrapping.build_wrappers`), so ``axm_call``
        inherits its full contract: kwarg unwrapping, implicit-path warning,
        tracing, exception flattening (a raised ``ValueError``/``OSError``
        becomes ``{success: False, error: ...}`` — never a raw MCP protocol
        error), and the success-only ``text`` short-circuit. This is the
        single execution path.

        The per-key concurrency lock (``git_*``/``protocol_*`` in HTTP mode)
        is only held via :meth:`acall`; ``call`` is the sync entry used in
        stdio mode and by tests.

        Args:
            name: Tool name.
            arguments: Keyword arguments for the tool.

        Returns:
            The tool's ``ToolResult.text`` when the result is successful, else a
            readable rendering of the shared flattened envelope.

        Raises:
            UnknownToolError: If *name* is not in the catalog.
        """
        tool = self._get(name)  # validate name → UnknownToolError
        self._bind_check(tool, arguments)
        sync_wrapper, _ = self._wrappers[name]
        return self._render(sync_wrapper(**(arguments or {})))

    async def acall(self, name: str, arguments: dict[str, object] | None = None) -> str:
        """Execute *name* through the lock-aware async wrapper.

        The HTTP-mode entry point: it awaits the async wrapper, so the
        per-key lock (``git_*`` by repo path, ``protocol_*`` by session) is
        held and the sync tool body runs on a worker thread via
        ``asyncio.to_thread`` — the event loop of the shared server is never
        blocked. In stdio mode the async wrapper simply runs the tool inline.

        Args:
            name: Tool name.
            arguments: Keyword arguments for the tool.

        Returns:
            The rendered text output (same contract as :meth:`call`).

        Raises:
            UnknownToolError: If *name* is not in the catalog.
        """
        tool = self._get(name)  # validate name → UnknownToolError
        self._bind_check(tool, arguments)
        _, async_wrapper = self._wrappers[name]
        result = await async_wrapper(**(arguments or {}))
        return self._render(result)

    @staticmethod
    def _bind_check(tool: ToolEntry, arguments: dict[str, object] | None) -> None:
        """Bind *arguments* to the tool's signature, raising ``TypeError`` early.

        Separates a genuine **argument mismatch** (missing required / unexpected
        keyword — the loss of client-side schema validation that ``axm_call``
        must compensate with a param hint) from a ``TypeError`` raised *inside*
        the tool body (which the wrapper catches and flattens). Only the former
        propagates here as a ``TypeError``; a dispatcher's ``**kwargs`` makes
        the bind permissive, so those tools never false-positive.
        """
        try:
            sig = inspect.signature(_exec_fn(tool))
        except (ValueError, TypeError):
            return  # un-introspectable signature — let the wrapper handle it
        sig.bind(**(arguments or {}))

    @staticmethod
    def _render(result: dict[str, object] | str) -> str:
        """Render a wrapper result (already flattened) to facade text."""
        if isinstance(result, str):
            return result
        return "\n".join(f"{k}: {v}" for k, v in result.items())

    def param_hint(self, name: str) -> str:
        """Human-readable list of accepted params for *name* (for error text)."""
        try:
            params = self._params(name)
        except UnknownToolError:
            return ""
        parts = [
            f"{p.name}: {p.annotation}" + ("" if p.required else f" = {p.default}")
            for p in params
        ]
        return ", ".join(parts)

    def _params(self, name: str) -> list[_ParamSpec]:
        """Typed parameter specs for *name* (shared by describe/param_hint)."""
        return [
            _ParamSpec(
                name=p.name,
                annotation=_annotation_str(p.annotation),
                required=p.default is inspect.Parameter.empty,
                default=(
                    None if p.default is inspect.Parameter.empty else repr(p.default)
                ),
            )
            for p in signature_params(_exec_fn(self._get(name)))
        ]

    def capabilities(self, domain: str | None = None) -> dict[str, list[str]]:
        """Group tool names by domain.

        Args:
            domain: When given, return only that domain's tools.

        Returns:
            ``{domain: [tool names]}``; tools without a domain are grouped
            under the ``"(ungrouped)"`` key.
        """
        groups: dict[str, list[str]] = {}
        for name in sorted(self._entries):
            d = tool_metadata(self._entries[name]).domain or "(ungrouped)"
            if domain is not None and d != domain:
                continue
            groups.setdefault(d, []).append(name)
        return groups

    # ── internals ────────────────────────────────────────────────────────

    def _get(self, name: str) -> ToolEntry:
        try:
            return self._entries[name]
        except KeyError as exc:
            known = ", ".join(sorted(self._entries))
            msg = f"Unknown tool {name!r}. Known tools: {known or '<none>'}"
            raise UnknownToolError(msg) from exc


def _annotation_str(annotation: object) -> str:
    """Render a parameter annotation compactly."""
    if annotation is inspect.Parameter.empty:
        return "Any"
    if isinstance(annotation, type):
        return annotation.__name__
    return str(annotation)
