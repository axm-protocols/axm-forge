"""FlowsHook — execution flow tracing with entry point detection.

Protocol hook that maps to the ``trace_flow`` and ``find_entry_points``
functionalities. Registered as ``ast:flows`` via ``axm.hooks`` entry point.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm.hooks.base import HookResult

logger = logging.getLogger(__name__)

__all__ = ["FlowsHook"]

# Lazy imports
get_package: Any = None
trace_flow: Any = None
find_entry_points: Any = None
build_callee_index: Any = None

_MAX_UNSCOPED_ENTRIES = 20


@dataclass
class _TraceOpts:
    """Bundled tracing options passed to _trace_entries / _trace_all."""

    max_depth: int = 5
    cross_module: bool = False
    detail: str = "trace"
    exclude_stdlib: bool = True


def _ensure_flow_imports() -> None:
    """Load lazy imports for flow tracing."""
    global get_package, trace_flow, find_entry_points, build_callee_index
    if get_package is not None:
        return
    from axm_ast.core.cache import get_package as _gp
    from axm_ast.core.flows import build_callee_index as _bci
    from axm_ast.core.flows import find_entry_points as _fep
    from axm_ast.core.flows import trace_flow as _tf

    get_package = _gp
    find_entry_points = _fep
    trace_flow = _tf
    build_callee_index = _bci


def _build_trace_opts(params: dict[str, Any]) -> tuple[_TraceOpts, bool]:
    """Build trace options and compact flag from hook parameters."""
    detail = str(params.get("detail", "trace"))
    is_compact = detail == "compact"
    opts = _TraceOpts(
        max_depth=int(params.get("max_depth", 5)),
        cross_module=bool(params.get("cross_module", False)),
        detail="trace" if is_compact else detail,
        exclude_stdlib=bool(params.get("exclude_stdlib", True)),
    )
    return opts, is_compact


def _parse_entry_symbols(entry: str) -> list[str]:
    """Parse a newline-separated entry string into unique symbol names."""
    return list(dict.fromkeys(s.strip() for s in entry.splitlines() if s.strip()))


def _trace_opts_kwargs(opts: _TraceOpts) -> dict[str, Any]:
    """Convert _TraceOpts to keyword arguments for trace_flow."""
    return {
        "max_depth": opts.max_depth,
        "cross_module": opts.cross_module,
        "detail": opts.detail,
        "exclude_stdlib": opts.exclude_stdlib,
    }


@dataclass
class FlowsHook:
    """Trace execution flows and detect entry points.

    Reads ``working_dir`` from *context*, and ``entry``, ``detail``,
    ``max_depth``, ``cross_module`` from *params*.

    When ``entry`` contains multiple symbols (newline-separated), each
    is traced independently using a shared pre-computed callee index.

    If ``entry`` is not provided, discovers entry points and traces
    them (excluding ``__all__`` exports, capped at 20).
    """

    def execute(self, context: dict[str, Any], **params: Any) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary (must contain ``working_dir``).
            **params:
                Optional ``entry`` (symbol name, or newline-separated list).
                Optional ``detail`` ("source", "trace", or "compact").
                Optional ``max_depth`` (default 5).
                Optional ``cross_module`` (default False).

        Returns:
            HookResult with ``traces`` dict/list in metadata on success.
        """
        path = params.get("path") or context.get("working_dir", ".")
        working_dir = Path(path).resolve()

        if not working_dir.is_dir():
            return HookResult.fail(f"working_dir not a directory: {working_dir}")

        opts, is_compact = _build_trace_opts(params)

        try:
            _ensure_flow_imports()
            pkg = get_package(working_dir)

            entry = params.get("entry")
            if entry is not None:
                return self._trace_entries(pkg, entry, opts, compact=is_compact)
            return self._trace_all(pkg, opts, compact=is_compact)

        except Exception as exc:  # noqa: BLE001
            return HookResult.fail(f"Flow tracing failed: {exc}")

    @staticmethod
    def _deduplicate_entry_symbols(symbols: list[str]) -> list[str]:
        """Remove parent classes when qualified methods are present."""
        qualified = {s for s in symbols if "." in s}
        parents = {s.rsplit(".", 1)[0] for s in qualified}
        return [s for s in symbols if s not in parents]

    @staticmethod
    def _format_symbol_traces(
        steps: list[Any],
        sym: str,
        compact: bool,
        format_fn: Any,
    ) -> Any:
        """Format traced steps as compact string or dict list."""
        if compact:
            return format_fn(steps)
        return [s.model_dump(exclude_none=True) for s in steps]

    @staticmethod
    def _trace_entries(
        pkg: Any,
        entry: str,
        opts: _TraceOpts,
        *,
        compact: bool = False,
    ) -> HookResult:
        """Trace one or more explicitly-specified entry symbols.

        For multi-symbol traces, callees already seen in a previous
        symbol's trace are deduplicated (first-wins ordering).
        Deduplication runs before compact/dict formatting.
        """
        from axm_ast.core.flows import format_flow_compact

        symbols = _parse_entry_symbols(entry)
        symbols = FlowsHook._deduplicate_entry_symbols(symbols)
        kw = _trace_opts_kwargs(opts)

        if len(symbols) == 1:
            steps = trace_flow(pkg, symbols[0], **kw)
            return HookResult.ok(
                traces=FlowsHook._format_symbol_traces(
                    steps,
                    symbols[0],
                    compact,
                    format_flow_compact,
                ),
            )

        return FlowsHook._trace_multi_entries(
            pkg,
            symbols,
            kw,
            compact,
            format_flow_compact,
        )

    @staticmethod
    def _trace_multi_entries(
        pkg: Any,
        symbols: list[str],
        kw: dict[str, Any],
        compact: bool,
        format_fn: Any,
    ) -> HookResult:
        """Trace multiple entry symbols with cross-trace deduplication."""
        index = build_callee_index(pkg)
        traces: dict[str, Any] = {}
        seen: set[str] = set()
        for sym in symbols:
            steps = trace_flow(pkg, sym, callee_index=index, **kw)
            if not steps:
                continue
            deduped = [s for s in steps if s.name == sym or s.name not in seen]
            seen.update(s.name for s in steps)
            traces[sym] = FlowsHook._format_symbol_traces(
                deduped,
                sym,
                compact,
                format_fn,
            )
        return HookResult.ok(traces=traces)

    @staticmethod
    def _trace_all(
        pkg: Any,
        opts: _TraceOpts,
        *,
        compact: bool = False,
    ) -> HookResult:
        """Discover entry points and trace them (with safety caps)."""
        from axm_ast.core.flows import format_flow_compact

        entries = find_entry_points(pkg)

        # Filter out __all__ exports — they're re-exports, not functional entry points
        entries = [e for e in entries if e.kind != "export"]

        if len(entries) > _MAX_UNSCOPED_ENTRIES:
            logger.warning(
                "ast:flows: %d entry points detected without explicit entry param, "
                "capping to %d. Pass 'entry' to target specific symbols.",
                len(entries),
                _MAX_UNSCOPED_ENTRIES,
            )
            entries = entries[:_MAX_UNSCOPED_ENTRIES]

        # Build index once for all entries
        index = build_callee_index(pkg)
        kw: dict[str, Any] = {
            "max_depth": opts.max_depth,
            "cross_module": opts.cross_module,
            "detail": opts.detail,
            "exclude_stdlib": opts.exclude_stdlib,
        }
        traces: dict[str, Any] = {}
        for e in entries:
            steps = trace_flow(pkg, e.name, callee_index=index, **kw)
            if steps:
                if compact:
                    traces[e.name] = format_flow_compact(steps)
                else:
                    traces[e.name] = [s.model_dump(exclude_none=True) for s in steps]

        return HookResult.ok(traces=traces)
