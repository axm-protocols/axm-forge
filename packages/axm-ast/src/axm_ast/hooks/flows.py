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


@dataclass
class FlowsHook:
    """Trace execution flows and detect entry points.

    Reads ``working_dir`` from *context*, and ``entry``, ``detail``,
    ``max_depth``, ``cross_module`` from *params*.

    If ``entry`` is not provided, discovers all entry points and traces
    from all of them. Detail defaults to "trace", but can be "source".
    If `detail` is "compact", it is mapped to "trace".
    Injects ``traces`` list into the session context.
    """

    def execute(self, context: dict[str, Any], **params: Any) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary (must contain ``working_dir``).
            **params:
                Optional ``entry`` (symbol name). Unfiltered if missing.
                Optional ``detail`` ("source", "trace", or "compact").
                Optional ``max_depth`` (default 5).
                Optional ``cross_module`` (default False).

        Returns:
            HookResult with ``traces`` dict/list in metadata on success.
            Or ``flow_trace`` representing the same semantic.
        """
        path = params.get("path") or context.get("working_dir", ".")
        working_dir = Path(path).resolve()

        if not working_dir.is_dir():
            return HookResult.fail(f"working_dir not a directory: {working_dir}")

        entry = params.get("entry")
        max_depth = int(params.get("max_depth", 5))
        cross_module = bool(params.get("cross_module", False))

        # detail translation ("compact" comes from spec, maps to "trace")
        detail = str(params.get("detail", "trace"))
        if detail == "compact":
            detail = "trace"

        try:
            # Lazy imports
            global get_package, trace_flow, find_entry_points
            if get_package is None:
                from axm_ast.core.cache import get_package as _gp
                from axm_ast.core.flows import find_entry_points as _fep
                from axm_ast.core.flows import trace_flow as _tf

                get_package = _gp
                find_entry_points = _fep
                trace_flow = _tf

            pkg = get_package(working_dir)

            if entry is not None:
                steps = trace_flow(
                    pkg,
                    entry,
                    max_depth=max_depth,
                    cross_module=cross_module,
                    detail=detail,
                )
                return HookResult.ok(
                    traces=[s.model_dump(exclude_none=True) for s in steps]
                )

            # Detect all entry points and trace them
            entries = find_entry_points(pkg)
            traces: dict[str, Any] = {}
            for e in entries:
                steps = trace_flow(
                    pkg,
                    e.name,
                    max_depth=max_depth,
                    cross_module=cross_module,
                    detail=detail,
                )
                if steps:
                    traces[e.name] = [s.model_dump(exclude_none=True) for s in steps]

            # A dict if entry point not specified, so we have multiple entry flows.
            # (Matches AC3 expectations: returns flow traces).
            return HookResult.ok(traces=traces)

        except Exception as exc:  # noqa: BLE001
            return HookResult.fail(f"Flow tracing failed: {exc}")
