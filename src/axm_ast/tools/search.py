"""SearchTool — semantic symbol search."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

__all__ = ["SearchTool"]


class SearchTool(AXMTool):
    """Search symbols by name, return type, kind, or base class.

    Registered as ``ast_search`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "ast_search"

    def execute(
        self,
        *,
        path: str = ".",
        name: str | None = None,
        returns: str | None = None,
        kind: str | None = None,
        inherits: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Search symbols across a package.

        Args:
            path: Path to package directory.
            name: Filter by symbol name (substring match).
            returns: Filter by return type.
            kind: Filter by kind (function, method, classmethod, etc.).
            inherits: Filter by base class name.

        Returns:
            ToolResult with matching symbols.
        """
        try:
            project_path = Path(path).resolve()
            if not project_path.is_dir():
                return ToolResult(
                    success=False, error=f"Not a directory: {project_path}"
                )

            from axm_ast.core.analyzer import analyze_package, search_symbols
            from axm_ast.models import FunctionKind

            pkg = analyze_package(project_path)

            kind_enum = None
            if kind:
                try:
                    kind_enum = FunctionKind(kind)
                except ValueError:
                    return ToolResult(
                        success=False,
                        error=f"Invalid kind: {kind}",
                    )

            results = search_symbols(
                pkg, name=name, returns=returns, kind=kind_enum, inherits=inherits
            )

            symbols = []
            for sym in results:
                entry: dict[str, Any] = {
                    "name": sym.name,
                    "module": getattr(sym, "module", ""),
                }
                if hasattr(sym, "signature"):
                    entry["signature"] = sym.signature
                if hasattr(sym, "return_type"):
                    entry["return_type"] = sym.return_type
                symbols.append(entry)

            return ToolResult(
                success=True,
                data={"results": symbols, "count": len(symbols)},
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
