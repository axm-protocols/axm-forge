"""ExtractTool — MCP tool wrapping :func:`extract_symbols` for agent use."""

from __future__ import annotations

import json
from pathlib import Path

from axm.tools.base import AXMTool, ToolResult

from axm_anvil.core.extract import extract_symbols
from axm_anvil.core.plan import MovePlan
from axm_anvil.tools._common import exception_to_result, normalize_execute_args

__all__ = ["ExtractTool"]


class ExtractTool(AXMTool):
    """Extract top-level symbols from a module into a brand-new module.

    Registered as ``anvil_extract`` via the ``axm.tools`` entry point.
    Delegates to :func:`axm_anvil.core.extract.extract_symbols` (itself a
    thin adapter over the move pipeline) and adapts exceptions into
    ``ToolResult(success=False)``. The result shape matches ``anvil_move``.
    """

    agent_hint: str = (
        "Extract classes, functions, or constants into a NEW module "
        "(created on disk), with their transitive dependencies, and rewrite "
        "cross-file callers. Use dry_run=True to preview changes."
    )

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "anvil_extract"

    @staticmethod
    def _parse_decorators(spec: str | None) -> frozenset[str] | None:
        if spec is None:
            return None
        return frozenset(entry.strip() for entry in spec.split(",") if entry.strip())

    @staticmethod
    def _build_result_data(
        plan: MovePlan,
        src_path: Path,
        tgt_path: Path,
    ) -> dict[str, object]:
        return {
            "moved": [{"symbol": name} for name in plan.moved_names],
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
        rename: str | None = None,
        strict: bool = False,
        insert_after: str | None = None,
        include_helpers: bool = True,
        side_effect_decorators: str | None = None,
        **kwargs: object,
    ) -> ToolResult:
        """Extract ``symbols`` (CSV) from ``from_file`` into a new ``to_file``.

        Parameters
        ----------
        path:
            Workspace root used to resolve relative ``from_file`` / ``to_file``
            and to constrain caller updates.
        symbols:
            Comma-separated list of top-level symbol names to extract. Empty
            entries are ignored.
        from_file:
            Source Python file. Relative paths are resolved against ``path``.
        to_file:
            Target Python file to **create**. Relative paths are resolved
            against ``path``; missing parent directories are created.
        dry_run:
            When ``True``, compute the :class:`MovePlan` without writing (and
            without leaving a scaffolded target on disk).
        shared_helpers:
            Policy for helpers used by both moved and remaining symbols:
            ``"duplicate"``, ``"extract"``, or ``"error"``.
        shared_helpers_module:
            Target module path used when ``shared_helpers="extract"``.
        rename:
            Optional JSON object string mapping old symbol names to new ones
            (e.g. ``'{"OldName": "NewName"}'``). Invalid JSON yields a
            ``success=False`` result.
        strict:
            When ``True``, a requested symbol absent from the source module
            raises (surfaced as ``success=False``) instead of being skipped
            with a warning.
        insert_after:
            Optional name of a top-level symbol in the target module after
            which extracted blocks are spliced. ``None`` appends at the end.
        include_helpers:
            When ``True`` (default) transitively-referenced local helpers and
            constants are copied into the target.
        side_effect_decorators:
            Optional comma-separated list of extra side-effect decorator
            dotted-names extending the built-in whitelist.

        Returns
        -------
        ToolResult
            ``success=True`` with a plan summary on success; otherwise
            ``success=False`` with a message (missing symbol, collision,
            shared helpers, validation error).
        """
        root, src_path, tgt_path, symbol_list = normalize_execute_args(
            path, symbols, from_file, to_file
        )

        extra_decorators = self._parse_decorators(side_effect_decorators)

        rename_map: dict[str, str] | None = None
        if rename is not None:
            try:
                rename_map = json.loads(rename)
            except json.JSONDecodeError as exc:
                return ToolResult(success=False, error=f"invalid JSON in rename: {exc}")

        try:
            plan = extract_symbols(
                src_path,
                tgt_path,
                symbol_list,
                dry_run=dry_run,
                workspace_root=root,
                shared_helpers=shared_helpers,
                shared_helpers_module=shared_helpers_module,
                rename=rename_map,
                strict=strict,
                insert_after=insert_after,
                include_helpers=include_helpers,
                side_effect_decorators=extra_decorators,
            )
        except Exception as exc:  # noqa: BLE001
            return exception_to_result(exc)

        data = self._build_result_data(plan, src_path, tgt_path)
        text = self._format_text(plan, from_file=str(src_path), to_file=str(tgt_path))
        return ToolResult(success=True, data=data, text=text)

    def _format_text(
        self,
        plan: MovePlan,
        *,
        from_file: str,
        to_file: str,
    ) -> str:
        """Render the extract plan as compact text (mirrors anvil_move)."""
        n = len(plan.moved_names)
        src_name = Path(from_file).name or from_file
        tgt_name = Path(to_file).name or to_file
        lines: list[str] = [
            f"anvil_extract | {n} symbols | {src_name} → {tgt_name} (new)",
            "",
            "Extracted:",
        ]
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
