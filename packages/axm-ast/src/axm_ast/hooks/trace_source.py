"""TraceSourceHook — enriched BFS trace with function source code.

Protocol hook that calls ``trace_flow(detail="source")`` and returns
the complete trace as ``HookResult`` metadata.  Registered as
``ast:trace-source`` via ``axm.hooks`` entry point.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm.hooks.base import HookResult

__all__ = ["TraceSourceHook"]


@dataclass
class TraceSourceHook:
    """Run ``trace_flow(detail="source")`` and return the enriched trace.

    Reads ``working_dir`` from *context* and ``entry`` from *params*.
    The result is injected into session context via ``inject_result``.
    """

    def execute(self, context: dict[str, Any], **params: Any) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary (must contain ``working_dir``).
            **params: Must include ``entry`` (symbol name to trace from).
                Optional ``max_depth`` (default 5), ``cross_module`` (default False).

        Returns:
            HookResult with ``trace`` list in metadata on success.
        """
        entry = params.get("entry")
        if not entry:
            return HookResult.fail("Missing required param 'entry'")

        working_dir = Path(context.get("working_dir", "."))
        if not working_dir.is_dir():
            return HookResult.fail(f"working_dir not a directory: {working_dir}")

        try:
            from axm_ast.core.analyzer import analyze_package
            from axm_ast.core.flows import trace_flow

            pkg = analyze_package(working_dir)
            max_depth = int(params.get("max_depth", 5))
            cross_module = bool(params.get("cross_module", False))

            steps = trace_flow(
                pkg,
                entry,
                max_depth=max_depth,
                cross_module=cross_module,
                detail="source",
            )
            return HookResult.ok(
                trace=[s.model_dump(exclude_none=True) for s in steps],
            )
        except Exception as exc:  # noqa: BLE001
            return HookResult.fail(f"Trace failed: {exc}")
