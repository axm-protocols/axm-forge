"""RenameTool — MCP tool wrapping :func:`rename_symbols` for agent-facing use."""

from __future__ import annotations

import json
from pathlib import Path

from axm.tools.base import AXMTool, ToolResult

from axm_anvil.core.plan import MoveValidationError, SymbolNotFoundError
from axm_anvil.core.rename import RenamePlan, rename_symbols

__all__ = ["RenameTool"]


class RenameTool(AXMTool):
    """Rename top-level symbols in place, rewriting cross-file callers.

    Registered as ``anvil_rename`` via the ``axm.tools`` entry point.
    Delegates to :func:`axm_anvil.core.rename.rename_symbols` and adapts
    exceptions into ``ToolResult(success=False)``. Mono-symbol renames use
    ``--old``/``--new``; batch renames pass a ``--mapping`` JSON object
    (symmetric with the ``rename`` JSON of :class:`MoveTool`). ``reexport``
    is not exposed (incompatible with rename, per ``MoveTool.execute``).
    """

    agent_hint: str = (
        "Rename a top-level symbol in place and rewrite its cross-file "
        "callers atomically. Use dry_run=True to preview changes."
    )

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "anvil_rename"

    @staticmethod
    def _resolve_mapping(
        mapping: str | None, old: str, new: str
    ) -> dict[str, str] | ToolResult:
        """Build the ``old -> new`` mapping from JSON or ``old``/``new`` args."""
        if mapping is not None:
            try:
                parsed = json.loads(mapping)
            except json.JSONDecodeError as exc:
                return ToolResult(
                    success=False, error=f"invalid JSON in mapping: {exc}"
                )
            if not isinstance(parsed, dict):
                return ToolResult(success=False, error="mapping must be a JSON object")
            return {str(k): str(v) for k, v in parsed.items()}
        if old and new:
            return {old: new}
        return ToolResult(
            success=False,
            error="provide --old and --new, or a --mapping JSON object",
        )

    @staticmethod
    def _build_result_data(plan: RenamePlan) -> dict[str, object]:
        return {
            "renamed": [{"old": old, "new": new} for old, new in plan.renamed.items()],
            "callers_updated": [
                {
                    "file": entry.file,
                    "line": entry.line,
                    "old": entry.old,
                    "new": entry.new,
                }
                for entry in plan.callers_updated
            ],
            "warnings": list(plan.warnings),
            "files_modified": list(plan.files_modified),
        }

    @staticmethod
    def _exception_to_result(exc: Exception) -> ToolResult:
        match exc:
            case SymbolNotFoundError():
                return ToolResult(
                    success=False,
                    error=f"Symbol {exc!s} not found in module",
                )
            case MoveValidationError():
                return ToolResult(success=False, error=str(exc))
            case _:
                return ToolResult(success=False, error=str(exc))

    def execute(  # noqa: PLR0913
        self,
        *,
        path: str = ".",
        file: str = "",
        old: str = "",
        new: str = "",
        mapping: str | None = None,
        dry_run: bool = False,
        strict: bool = False,
        **kwargs: object,
    ) -> ToolResult:
        """Rename symbol(s) in ``file`` and rewrite cross-file callers.

        Parameters
        ----------
        path:
            Workspace root used to resolve a relative ``file`` and to
            constrain caller discovery.
        file:
            Python file defining the symbols. Relative paths resolve against
            ``path``.
        old / new:
            Mono-symbol rename: rename ``old`` to ``new``. Ignored when
            ``mapping`` is provided.
        mapping:
            Optional JSON object string mapping old names to new ones
            (e.g. ``'{"OldName": "NewName"}'``) for batch renames. Invalid
            JSON yields a ``success=False`` result.
        dry_run:
            When ``True``, compute the :class:`RenamePlan` without writing.
        strict:
            When ``True`` an absent symbol raises (surfaced as
            ``success=False``); when ``False`` (default) it is skipped with
            a warning.

        Returns
        -------
        ToolResult
            ``success=True`` with a rename summary (``renamed``,
            ``callers_updated``, ``warnings``, ``files_modified``) on
            success; otherwise ``success=False`` with a failure message.
        """
        resolved = self._resolve_mapping(mapping, old, new)
        if isinstance(resolved, ToolResult):
            return resolved
        root = Path(path).resolve()
        src_path = Path(file)
        if not src_path.is_absolute():
            src_path = root / src_path

        try:
            plan = rename_symbols(
                root,
                src_path,
                resolved,
                dry_run=dry_run,
                workspace_root=root,
                strict=strict,
            )
        except Exception as exc:  # noqa: BLE001
            return self._exception_to_result(exc)

        data = self._build_result_data(plan)
        text = self._format_text(plan, file=str(src_path))
        return ToolResult(success=True, data=data, text=text)

    def _format_text(self, plan: RenamePlan, *, file: str) -> str:
        """Render the rename plan as compact text (mirrors anvil_move)."""
        n = len(plan.renamed)
        name = Path(file).name or file
        lines: list[str] = [f"anvil_rename | {n} symbols | {name}", ""]
        lines.append("Renamed:")
        for old, new in plan.renamed.items():
            lines.append(f"  - {old} → {new}")
        lines.append("")
        lines.append(f"Callers Updated: {len(plan.callers_updated)}")
        if plan.warnings:
            lines.append("")
            lines.append("Warnings:")
            for warning in plan.warnings:
                lines.append(f"  - {warning}")
        return "\n".join(lines)
