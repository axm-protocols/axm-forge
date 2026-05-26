"""MoveTool — MCP tool wrapping :func:`move_symbols` for agent-facing use."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

from axm_anvil.core.move import (
    SymbolAlreadyExistsError,
    SymbolNotFoundError,
    move_symbols,
)
from axm_anvil.core.plan import ImportCycleError, MovePlan, SharedHelpersError

__all__ = ["MoveTool"]


class MoveTool(AXMTool):
    """Move top-level symbols between Python files atomically.

    Registered as ``ast_move`` via the ``axm.tools`` entry point.
    Delegates to :func:`axm_anvil.core.move.move_symbols` and adapts
    exceptions into ``ToolResult(success=False)``.
    """

    agent_hint: str = (
        "Move classes, functions, or constants between Python files atomically. "
        "Use dry_run=True to preview changes."
    )

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "ast_move"

    @staticmethod
    def _normalize_execute_args(
        path: str,
        symbols: str,
        from_file: str,
        to_file: str,
    ) -> tuple[Path, Path, Path, list[str]]:
        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
        root = Path(path).resolve()
        src_path = Path(from_file)
        tgt_path = Path(to_file)
        if not src_path.is_absolute():
            src_path = root / src_path
        if not tgt_path.is_absolute():
            tgt_path = root / tgt_path
        return root, src_path, tgt_path, symbol_list

    @staticmethod
    def _exception_to_result(exc: Exception) -> ToolResult:
        match exc:
            case SymbolNotFoundError():
                return ToolResult(
                    success=False,
                    error=f"Symbol {exc!s} not found in source module",
                )
            case SymbolAlreadyExistsError():
                return ToolResult(
                    success=False,
                    error=f"Symbol {exc!s} already exists in target module",
                )
            case SharedHelpersError():
                joined = ", ".join(exc.shared_helpers)
                return ToolResult(
                    success=False,
                    error=f"Shared helpers detected: {joined}",
                )
            case ImportCycleError():
                return ToolResult(success=False, error=str(exc))
            case _:
                return ToolResult(success=False, error=str(exc))

    def execute(  # noqa: PLR0913
        self,
        *,
        path: str = ".",
        symbols: str = "",
        from_file: str = "",
        to_file: str = "",
        dry_run: bool = False,
        shared_helpers: str = "duplicate",
        shared_helpers_module: str | None = None,
        reexport: bool = False,
        check: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        """Move ``symbols`` (CSV) from ``from_file`` to ``to_file``.

        Parameters
        ----------
        path:
            Workspace root used to resolve relative ``from_file`` / ``to_file``
            and to constrain caller updates.
        symbols:
            Comma-separated list of top-level symbol names to move. Empty
            entries are ignored.
        from_file:
            Source Python file. Relative paths are resolved against ``path``.
        to_file:
            Target Python file. Relative paths are resolved against ``path``.
        dry_run:
            When ``True``, compute the :class:`MovePlan` without writing.
        shared_helpers:
            Policy for helpers used by both moved and remaining symbols:
            ``"duplicate"``, ``"extract"``, or ``"error"``.
        shared_helpers_module:
            Target module path used when ``shared_helpers="extract"``.

        Returns
        -------
        ToolResult
            ``success=True`` with a ``MovePlan`` summary on success; otherwise
            ``success=False`` with a message describing the failure
            (missing symbol, collision, shared helpers, validation error).
        """
        root, src_path, tgt_path, symbol_list = self._normalize_execute_args(
            path, symbols, from_file, to_file
        )

        try:
            plan = move_symbols(
                src_path,
                tgt_path,
                symbol_list,
                dry_run=dry_run,
                workspace_root=root,
                shared_helpers=shared_helpers,
                shared_helpers_module=shared_helpers_module,
                reexport=reexport,
                check=check,
            )
        except Exception as exc:  # noqa: BLE001
            return self._exception_to_result(exc)

        data: dict[str, Any] = {
            "moved": [
                {"symbol": name, "from_lines": [], "to_lines": []}
                for name in plan.moved_names
            ],
            "dependencies_copied": {
                "imports": list(plan.imports_added),
                "constants": list(plan.constants_added),
            },
            "callers_updated": [
                {
                    "file": entry.file,
                    "line": entry.line,
                    "old": entry.old,
                    "new": entry.new,
                }
                for entry in plan.callers_updated
            ],
            "orphans_removed": [],
            "warnings": list(plan.warnings),
            "shared_helpers_detected": [
                {
                    "name": det.name,
                    "used_by_moved": list(det.used_by_moved),
                    "used_by_remaining": list(det.used_by_remaining),
                }
                for det in plan.shared_helpers_detected
            ],
            "files_modified": [str(src_path), str(tgt_path)],
        }
        if reexport:
            data["reexport"] = True
        if check:
            data["check"] = True
        text = self._format_text(
            plan,
            from_file=str(src_path),
            to_file=str(tgt_path),
            reexport=reexport,
        )
        return ToolResult(success=True, data=data, text=text)

    def _format_text(
        self,
        plan: MovePlan,
        *,
        from_file: str,
        to_file: str,
        reexport: bool = False,
    ) -> str:
        """Render the move plan as compact text per spec §14.2."""
        n = len(plan.moved_names)
        src_name = Path(from_file).name or from_file
        tgt_name = Path(to_file).name or to_file
        lines: list[str] = [
            f"ast_move | {n} symbols | {src_name} \u2192 {tgt_name}",
            "",
        ]
        if reexport:
            lines.append("Mode: reexport")
            lines.append("")
        lines.append("Moved:")
        for name in plan.moved_names:
            lines.append(f"  - {name}")
        lines.append("")
        lines.append("Dependencies:")
        lines.append(f"  imports: {len(plan.imports_added)}")
        lines.append(f"  constants: {len(plan.constants_added)}")
        lines.append("")
        lines.append(f"Callers Updated: {len(plan.callers_updated)}")
        if plan.shared_helpers_detected:
            lines.append("")
            lines.append("Shared Helpers:")
            for det in plan.shared_helpers_detected:
                lines.append(
                    f"  - {det.name} (also used by: {', '.join(det.used_by_remaining)})"
                )
        if plan.warnings:
            lines.append("")
            lines.append("Warnings:")
            for warning in plan.warnings:
                lines.append(f"  - {warning}")
        return "\n".join(lines)
