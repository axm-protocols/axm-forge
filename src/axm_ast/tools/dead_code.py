"""DeadCodeTool — detect unreferenced symbols in a package."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

__all__ = ["DeadCodeTool"]


class DeadCodeTool(AXMTool):
    """Detect dead (unreferenced) code symbols in a Python package.

    Registered as ``ast_dead_code`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "ast_dead_code"

    def execute(self, *, path: str = ".", **kwargs: Any) -> ToolResult:
        """Find dead code in a Python package.

        Args:
            path: Path to package directory.
            include_tests: Include test fixtures in scan (default False).

        Returns:
            ToolResult with dead symbols list.
        """
        try:
            pkg_path = Path(path).resolve()
            if not pkg_path.is_dir():
                return ToolResult(success=False, error=f"Not a directory: {pkg_path}")

            from axm_ast.core.cache import get_package
            from axm_ast.core.dead_code import find_dead_code

            include_tests = bool(kwargs.get("include_tests", False))
            pkg = get_package(pkg_path)
            dead = find_dead_code(pkg, include_tests=include_tests)

            return ToolResult(
                success=True,
                data={
                    "dead_symbols": [
                        {
                            "name": d.name,
                            "module_path": d.module_path,
                            "line": d.line,
                            "kind": d.kind,
                        }
                        for d in dead
                    ],
                    "total": len(dead),
                },
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
