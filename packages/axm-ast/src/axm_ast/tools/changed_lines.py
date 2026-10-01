"""Map changed line intervals to symbols in an immutable snapshot."""

from __future__ import annotations

from pathlib import Path

from axm.tools.base import AXMTool, ToolResult

from axm_ast.core.changed_lines import symbols_for_lines

__all__ = ["ChangedLinesTool"]

_INTERVAL_SIZE = 2


class ChangedLinesTool(AXMTool):
    """Expose the hunk-to-symbol measurement for graph and MCP consumers."""

    @property
    def name(self) -> str:
        return "ast_changed_lines"

    def execute(
        self,
        path: str = ".",
        file: str = "",
        intervals: list[list[int]] | None = None,
        **kwargs: object,
    ) -> ToolResult:
        """Resolve package-relative lines; intervals are [start, count] pairs."""
        root = Path(path).resolve()
        target = (root / file).resolve()
        if not target.is_relative_to(root):
            return ToolResult(success=False, error="file is outside package")
        if any(
            len(pair) != _INTERVAL_SIZE or min(pair) < 0 for pair in intervals or []
        ):
            return ToolResult(
                success=False, error="expected non-negative [start, count]"
            )
        try:
            symbols = symbols_for_lines(
                root, target, [(p[0], p[1]) for p in intervals or []]
            )
        except (ValueError, OSError) as exc:
            return ToolResult(success=False, error=str(exc))
        return ToolResult(
            success=True, data={"symbols": list(symbols)}, text="\n".join(symbols)
        )
