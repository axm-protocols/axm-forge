"""FlowsHook — execution flow tracing with entry point detection.

Protocol hook that maps to the ``trace_flow`` and ``find_entry_points``
functionalities. Registered as ``ast:flows`` via ``axm.hooks`` entry point.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict, cast

from axm.hooks.base import HookResult

from axm_ast.hooks._trace_protocol import _TraceFlow

if TYPE_CHECKING:
    from axm_ast.core.flows import EntryPoint, FlowStep
    from axm_ast.models.calls import CallSite
    from axm_ast.models.nodes import PackageInfo

logger = logging.getLogger(__name__)

__all__ = ["FlowsHook"]


class _TraceKwargs(TypedDict):
    """Keyword arguments forwarded to ``trace_flow``."""

    max_depth: int
    cross_module: bool
    detail: str
    exclude_stdlib: bool


# Concrete value type held in the ``traces`` mapping returned to callers:
# either a list of model-dumped FlowStep dicts, or a compact string
# representation when ``detail='compact'``.
_TraceValue = list[dict[str, object]] | str


@dataclass
class _FormatOpts:
    """Presentation options for trace output."""

    compact: bool
    format_fn: Callable[[list[FlowStep]], str]


# Lazy imports — populated on first ``execute`` call to keep import
# cost out of hook discovery. Typed as Callable so static analysis
# tracks signatures; ``None`` sentinel triggers the one-time load.
get_package: Callable[[Path], PackageInfo] | None = None
trace_flow: _TraceFlow | None = None
find_entry_points: Callable[[PackageInfo], list[EntryPoint]] | None = None
build_callee_index: (
    Callable[[PackageInfo], dict[tuple[str, str], list[CallSite]]] | None
) = None

_MAX_UNSCOPED_ENTRIES = 20


def _concat_compact_traces(traces: dict[str, _TraceValue]) -> str:
    """Join per-symbol compact trace strings into a single output."""
    return "\n".join(f"{sym}:\n{body}" for sym, body in traces.items())


def _discover_entries(pkg: PackageInfo) -> list[EntryPoint]:
    """Find entry points, drop ``__all__`` exports, cap at safety threshold."""
    assert find_entry_points is not None
    entries = [e for e in find_entry_points(pkg) if e.kind != "export"]
    if len(entries) > _MAX_UNSCOPED_ENTRIES:
        logger.warning(
            "ast:flows: %d entry points detected without explicit entry param, "
            "capping to %d. Pass 'entry' to target specific symbols.",
            len(entries),
            _MAX_UNSCOPED_ENTRIES,
        )
        entries = entries[:_MAX_UNSCOPED_ENTRIES]
    return entries


def _trace_entries_to_values(
    pkg: PackageInfo,
    entries: list[EntryPoint],
    index: dict[tuple[str, str], list[CallSite]],
    kw: _TraceKwargs,
    fmt: _FormatOpts,
) -> dict[str, _TraceValue]:
    """Trace each entry and format steps as compact string or dict list."""
    assert trace_flow is not None
    traces: dict[str, _TraceValue] = {}
    for e in entries:
        steps, _truncated = trace_flow(pkg, e.name, callee_index=index, **kw)
        if not steps:
            continue
        if fmt.compact:
            traces[e.name] = fmt.format_fn(steps)
        else:
            traces[e.name] = [
                cast("dict[str, object]", s.model_dump(exclude_none=True))
                for s in steps
            ]
    return traces


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


def build_trace_opts(params: dict[str, object]) -> tuple[_TraceOpts, bool]:
    """Build trace options and compact flag from hook parameters."""
    from axm_ast.core.flows import VALID_DETAILS

    detail = str(params.get("detail", "trace"))
    if detail not in VALID_DETAILS:
        msg = f"Invalid detail={detail!r}; must be one of {sorted(VALID_DETAILS)}"
        raise ValueError(msg)
    is_compact = detail == "compact"
    raw_max_depth = params.get("max_depth", 5)
    max_depth = int(raw_max_depth) if isinstance(raw_max_depth, (int, str)) else 5
    opts = _TraceOpts(
        max_depth=max_depth,
        cross_module=bool(params.get("cross_module", False)),
        detail=detail,
        exclude_stdlib=bool(params.get("exclude_stdlib", True)),
    )
    return opts, is_compact


def _parse_entry_symbols(entry: str) -> list[str]:
    """Parse a newline-separated entry string into unique symbol names."""
    return list(dict.fromkeys(s.strip() for s in entry.splitlines() if s.strip()))


def _trace_opts_kwargs(opts: _TraceOpts) -> _TraceKwargs:
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

    # ``context``/``params`` are heterogeneous user payloads; ``object``
    # forces explicit narrowing at every read site (mirrors hooks/context.py).
    def execute(self, context: dict[str, object], **params: object) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary (must contain ``working_dir``).
            **params:
                Optional ``entry`` (symbol name, or newline-separated list).
                Optional ``detail`` ("source", "trace", or "compact").
                Optional ``max_depth`` (default 5).
                Optional ``cross_module`` (default False).

        Returns:
            HookResult with ``traces`` in metadata on success.
            When *detail* is ``"compact"``, ``traces`` is a single string
            (concatenated with entry-name headers for multi-symbol traces).
            Otherwise, ``traces`` is a dict of symbol → step-dicts.
        """
        raw_path = params.get("path") or context.get("working_dir", ".")
        if not isinstance(raw_path, (str, Path)):
            return HookResult.fail(
                f"path must be str or Path, got {type(raw_path).__name__}"
            )
        working_dir = Path(raw_path).resolve()

        if not working_dir.is_dir():
            return HookResult.fail(f"working_dir not a directory: {working_dir}")

        try:
            opts, is_compact = build_trace_opts(params)
            _ensure_flow_imports()
            assert get_package is not None
            pkg = get_package(working_dir)

            entry = params.get("entry")
            if entry is not None:
                if not isinstance(entry, str):
                    return HookResult.fail(
                        f"entry must be str, got {type(entry).__name__}"
                    )
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
        steps: list[FlowStep],
        sym: str,
        compact: bool,
        format_fn: Callable[[list[FlowStep]], str],
    ) -> _TraceValue:
        """Format traced steps as compact string or dict list."""
        if compact:
            return format_fn(steps)
        # ``model_dump`` is upstream-typed ``dict[str, Any]`` (pydantic);
        # cast to ``dict[str, object]`` at this boundary.
        return [
            cast("dict[str, object]", s.model_dump(exclude_none=True)) for s in steps
        ]

    @staticmethod
    def _trace_entries(
        pkg: PackageInfo,
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

        assert trace_flow is not None

        symbols = _parse_entry_symbols(entry)
        symbols = FlowsHook._deduplicate_entry_symbols(symbols)
        kw = _trace_opts_kwargs(opts)

        if len(symbols) == 1:
            try:
                steps, _truncated = trace_flow(pkg, symbols[0], **kw)
            except ValueError as exc:
                return HookResult.fail(str(exc))
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
        pkg: PackageInfo,
        symbols: list[str],
        kw: _TraceKwargs,
        compact: bool,
        format_fn: Callable[[list[FlowStep]], str],
    ) -> HookResult:
        """Trace multiple entry symbols with cross-trace deduplication."""
        assert build_callee_index is not None
        assert trace_flow is not None

        index = build_callee_index(pkg)
        traces: dict[str, _TraceValue] = {}
        seen: set[str] = set()
        for sym in symbols:
            try:
                steps, _truncated = trace_flow(pkg, sym, callee_index=index, **kw)
            except ValueError:
                continue
            deduped = [s for s in steps if s.name == sym or s.name not in seen]
            seen.update(s.name for s in steps)
            traces[sym] = FlowsHook._format_symbol_traces(
                deduped,
                sym,
                compact,
                format_fn,
            )
        if compact:
            return HookResult.ok(
                traces=_concat_compact_traces(traces),
            )
        return HookResult.ok(traces=traces)

    @staticmethod
    def _trace_all(
        pkg: PackageInfo,
        opts: _TraceOpts,
        *,
        compact: bool = False,
    ) -> HookResult:
        """Discover entry points and trace them (with safety caps)."""
        from axm_ast.core.flows import format_flow_compact

        assert find_entry_points is not None
        assert build_callee_index is not None
        assert trace_flow is not None

        entries = _discover_entries(pkg)
        index = build_callee_index(pkg)
        kw = _trace_opts_kwargs(opts)
        traces = _trace_entries_to_values(
            pkg,
            entries,
            index,
            kw,
            _FormatOpts(compact=compact, format_fn=format_flow_compact),
        )

        if compact:
            return HookResult.ok(traces=_concat_compact_traces(traces))
        return HookResult.ok(traces=traces)
