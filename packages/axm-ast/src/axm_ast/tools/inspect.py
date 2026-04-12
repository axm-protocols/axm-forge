"""InspectTool — inspect a single symbol by name."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

from .inspect_detail import (
    build_detail,
    class_detail,
    function_detail,
    variable_detail,
)
from .inspect_resolve import (
    find_symbol_abs_path,
    find_symbol_file,
    inspect_dotted,
    inspect_module,
    resolve_module,
    resolve_path,
)
from .inspect_text import render_batch_text, render_symbol_text

logger = logging.getLogger(__name__)

__all__ = ["InspectTool"]


class InspectTool(AXMTool):
    """Inspect a symbol across the package without knowing its file.

    Registered as ``ast_inspect`` via axm.tools entry point.
    """

    agent_hint: str = (
        "Get full detail of a symbol by name,"
        " without knowing the file."
        " Returns file, start_line, end_line."
        " Use source=True to include source code."
        " Supports dotted paths like ClassName.method."
        " You can also pass a list of names via `symbols` for batch inspection."
    )

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "ast_inspect"

    def execute(
        self,
        *,
        path: str = ".",
        symbol: str | None = None,
        symbols: list[str] | None = None,
        source: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        """Inspect a symbol by name.

        Args:
            path: Path to package directory.
            symbol: Symbol name to inspect (required if symbols is not provided).
                Supports dotted paths like ``ClassName.method``.
            symbols: Optional list of symbol names for batch inspection.
            source: If True, include source code in the response.

        Returns:
            ToolResult with symbol details.
        """
        if not symbol and not symbols:
            return ToolResult(
                success=False, error="symbol or symbols parameter is required"
            )

        source = bool(source)

        try:
            project_path = resolve_path(path)
            if isinstance(project_path, ToolResult):
                return project_path

            if symbols is not None:
                return self._inspect_batch(project_path, symbols, source=source)

            return self._inspect_symbol(project_path, symbol, source=source)  # type: ignore[arg-type]
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

    def _inspect_batch(
        self,
        project_path: Path,
        symbols: list[str],
        *,
        source: bool,
    ) -> ToolResult:
        """Inspect multiple symbols in batch."""
        if not isinstance(symbols, list):
            return ToolResult(success=False, error="symbols parameter must be a list")
        results: list[dict[str, Any]] = []
        for sym in symbols:
            res = self._inspect_symbol(project_path, sym, source=source)
            if res.success and res.data and "symbol" in res.data:
                results.append(res.data["symbol"])
            else:
                results.append({"name": sym, "error": res.error})
        try:
            text = render_batch_text(results)
        except (KeyError, TypeError):
            text = None
        return ToolResult(
            success=True,
            data={"symbols": results},
            text=text,
        )

    def _inspect_symbol(
        self, project_path: Path, symbol: str, *, source: bool = False
    ) -> ToolResult:
        """Core symbol inspection logic."""
        from axm_ast.core.analyzer import search_symbols
        from axm_ast.core.cache import get_package

        pkg = get_package(project_path)

        if "." in symbol:
            return inspect_dotted(pkg, symbol, source=source)

        # --- Simple name: function or class ---
        results = search_symbols(
            pkg,
            name=symbol,
            returns=None,
            kind=None,
            inherits=None,
        )

        if not results:
            # --- Module fallback ---
            mod_result = inspect_module(pkg, symbol, source=source)
            if mod_result is not None:
                return mod_result
            return ToolResult(
                success=False,
                error=f"Symbol '{symbol}' not found",
            )

        _, sym = results[0]
        file_path = find_symbol_file(pkg, sym)
        abs_path = find_symbol_abs_path(pkg, sym)
        detail = build_detail(sym, file=file_path, abs_path=abs_path, source=source)
        return ToolResult(
            success=True,
            data={"symbol": detail},
            text=render_symbol_text(detail),
        )

    # --- Backward-compatible static aliases for extracted helpers ---

    _find_symbol_file = staticmethod(find_symbol_file)
    _find_symbol_abs_path = staticmethod(find_symbol_abs_path)
    _build_detail = staticmethod(build_detail)
    _variable_detail = staticmethod(variable_detail)
    _function_detail = staticmethod(function_detail)
    _class_detail = staticmethod(class_detail)
    _resolve_module = staticmethod(resolve_module)
