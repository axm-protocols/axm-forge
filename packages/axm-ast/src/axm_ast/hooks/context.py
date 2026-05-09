"""ContextHook — one-shot project context dump.

Protocol hook that calls ``build_context`` and returns the complete
project context as ``HookResult`` metadata. Registered as
``ast:context`` via ``axm.hooks`` entry point.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from axm.hooks.base import HookResult

if TYPE_CHECKING:
    from axm_ast.core.context import ContextResult, FormattedContext
    from axm_ast.core.workspace import WorkspaceContext
    from axm_ast.models.nodes import WorkspaceInfo


class _FormatContextJson(Protocol):
    """Protocol for ``format_context_json`` (kw-only ``depth``)."""

    def __call__(
        self, ctx: ContextResult, *, depth: int | None = None
    ) -> FormattedContext: ...


logger = logging.getLogger(__name__)

__all__ = ["ContextHook"]

# Lazy imports — populated on first ``execute`` call to keep import
# cost out of hook discovery. Typed as Callable so static analysis
# tracks signatures; ``None`` sentinel triggers the one-time load.
build_context: Callable[[Path], ContextResult] | None = None
format_context_json: _FormatContextJson | None = None
detect_workspace: Callable[[Path], WorkspaceInfo | None] | None = None
build_workspace_context: Callable[[Path], WorkspaceContext] | None = None


def _validate_context_params(
    context: dict[str, object],
    params: dict[str, object],
) -> tuple[Path, int | None] | HookResult:
    """Validate path and depth params; return (path, depth) or HookResult.fail."""
    raw_path = params.get("path") or context.get("working_dir", ".")
    if not isinstance(raw_path, (str, Path)):
        return HookResult.fail(
            f"path must be str or Path, got {type(raw_path).__name__}"
        )
    working_dir = Path(raw_path).resolve()
    if not working_dir.is_dir():
        return HookResult.fail(f"working_dir not a directory: {working_dir}")

    raw_depth = params.get("depth")
    if raw_depth is not None and not isinstance(raw_depth, int):
        return HookResult.fail(
            f"depth must be int or None, got {type(raw_depth).__name__}"
        )
    return working_dir, raw_depth


def _ensure_context_imports() -> None:
    """Load lazy imports for context building."""
    global build_context, format_context_json, detect_workspace, build_workspace_context
    if build_context is not None:
        return
    from axm_ast.core.context import build_context as _bc
    from axm_ast.core.context import format_context_json as _fcj
    from axm_ast.core.workspace import build_workspace_context as _bwc
    from axm_ast.core.workspace import detect_workspace as _dw

    build_context = _bc
    format_context_json = _fcj
    detect_workspace = _dw
    build_workspace_context = _bwc


@dataclass
class ContextHook:
    """Run one-shot project context dump.

    Reads ``path`` from *params* (or ``working_dir`` from context).
    Supports ``depth`` parameter (int | None) to control output granularity
    (0 = compact, 1 = packages, None = full).
    Workspace-aware: if path is a uv workspace root, returns workspace-level context.
    The result is injected into session context via ``inject_result``.
    """

    def execute(self, context: dict[str, object], **params: object) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary (must contain ``working_dir``).
            **params: Optional ``path`` (overrides ``working_dir``).
                Optional ``depth`` (int | None, default None) to control output
                granularity (0 = compact, 1 = packages, None = full).

        Returns:
            HookResult with ``project_context`` dict in metadata on success.
        """
        validated = _validate_context_params(context, params)
        if isinstance(validated, HookResult):
            return validated
        working_dir, depth = validated

        try:
            _ensure_context_imports()
            assert build_context is not None
            assert detect_workspace is not None
            assert build_workspace_context is not None
            assert format_context_json is not None

            ws = detect_workspace(working_dir)
            if ws is not None:
                ws_ctx = build_workspace_context(working_dir)
                return HookResult.ok(project_context=ws_ctx)

            ctx = build_context(working_dir)
            formatted = format_context_json(ctx, depth=depth)

            return HookResult.ok(project_context=formatted)
        except Exception as exc:  # noqa: BLE001
            return HookResult.fail(f"Context hook failed: {exc}")
