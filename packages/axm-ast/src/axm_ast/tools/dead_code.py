"""DeadCodeTool — detect unreferenced symbols in a package."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TypedDict

from axm.tools.base import AXMTool, ToolResult

from axm_ast.tools._base import safe_execute

logger = logging.getLogger(__name__)

__all__ = ["DeadCodeTool", "DeadSymbolEntry"]


class DeadSymbolEntry(TypedDict):
    """Serialized dead-symbol record for ``ast_dead_code`` output."""

    name: str
    module_path: str
    line: int
    kind: str


_KIND_SHORT = {"function": "func", "method": "meth", "class": "class"}


class DeadCodeTool(AXMTool):
    """Detect dead (unreferenced) code symbols in a Python package.

    Registered as ``ast_dead_code`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "ast_dead_code"

    @safe_execute
    def execute(
        self,
        *,
        path: str = ".",
        include_tests: bool = False,
        **kwargs: object,
    ) -> ToolResult:
        """Find dead code in a Python package.

        Args:
            path: Path to package directory.
            include_tests: Include test fixtures in scan (default False).

        Returns:
            ToolResult with dead symbols list.
        """
        pkg_path = Path(path).resolve()
        if not pkg_path.is_dir():
            return ToolResult(success=False, error=f"Not a directory: {pkg_path}")

        from axm_ast.core.cache import get_package
        from axm_ast.core.dead_code import find_dead_code

        pkg = get_package(pkg_path)
        dead = find_dead_code(pkg, include_tests=include_tests)

        symbols: list[DeadSymbolEntry] = [
            {
                "name": d.name,
                "module_path": d.module_path,
                "line": d.line,
                "kind": d.kind,
            }
            for d in dead
        ]

        return ToolResult(
            success=True,
            data={"dead_symbols": symbols, "total": len(dead)},
            text=self._render_text(symbols, pkg_root=str(pkg_path)),
        )

    @staticmethod
    def _render_text(symbols: list[DeadSymbolEntry], *, pkg_root: str) -> str:
        """Render dead symbols as compact text for token-efficient MCP responses."""
        header = f"ast_dead_code | {len(symbols)} dead symbols"
        if not symbols:
            return header
        prefix = pkg_root.rstrip("/") + "/"
        lines = [header, ""]
        for s in symbols:
            mod = s["module_path"]
            if mod.startswith(prefix):
                mod = mod[len(prefix) :]
            kind = _KIND_SHORT.get(s["kind"], s["kind"])
            lines.append(f"{kind:5s} {s['name']}  {mod}:{s['line']}")
        return "\n".join(lines)
