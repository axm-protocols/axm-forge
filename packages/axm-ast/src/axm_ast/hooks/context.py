"""ContextHook — one-shot project context dump.

Protocol hook that calls ``build_context`` and returns the complete
project context as ``HookResult`` metadata. Registered as
``ast:context`` via ``axm.hooks`` entry point.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm.hooks.base import HookResult

logger = logging.getLogger(__name__)

__all__ = ["ContextHook"]

# Lazy imports
build_context: Any = None
format_context_json: Any = None
detect_workspace: Any = None
build_workspace_context: Any = None


@dataclass
class ContextHook:
    """Run one-shot project context dump.

    Reads ``path`` from *params* (or ``working_dir`` from context).
    Supports ``slim`` parameter (bool) to limit depth to 0 for a compact output.
    Workspace-aware: if path is a uv workspace root, returns workspace-level context.
    The result is injected into session context via ``inject_result``.
    """

    def execute(self, context: dict[str, Any], **params: Any) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary (must contain ``working_dir``).
            **params: Optional ``path`` (overrides ``working_dir``).
                Optional ``slim`` (bool, default False) to limit output depth.

        Returns:
            HookResult with ``project_context`` dict in metadata on success.
        """
        path = params.get("path") or context.get("working_dir", ".")
        working_dir = Path(path).resolve()

        if not working_dir.is_dir():
            return HookResult.fail(f"working_dir not a directory: {working_dir}")

        slim = bool(params.get("slim", False))
        depth = 0 if slim else None

        try:
            # Lazy imports
            global \
                build_context, \
                format_context_json, \
                detect_workspace, \
                build_workspace_context
            if build_context is None:
                from axm_ast.core.context import build_context as _bc
                from axm_ast.core.context import format_context_json as _fcj
                from axm_ast.core.workspace import build_workspace_context as _bwc
                from axm_ast.core.workspace import detect_workspace as _dw

                build_context = _bc
                format_context_json = _fcj
                detect_workspace = _dw
                build_workspace_context = _bwc

            ws = detect_workspace(working_dir)
            if ws is not None:
                ctx = build_workspace_context(working_dir)
                return HookResult.ok(project_context=ctx)

            ctx = build_context(working_dir)
            formatted = format_context_json(ctx, depth=depth)

            return HookResult.ok(project_context=formatted)
        except Exception as exc:  # noqa: BLE001
            return HookResult.fail(f"Context hook failed: {exc}")
