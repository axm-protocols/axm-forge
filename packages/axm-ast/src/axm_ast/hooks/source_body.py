"""SourceBodyHook — symbol body extraction with line numbers.

Protocol hook that extracts the full source body of one or more symbols,
returning file path, start/end lines, and complete source code.  Registered
as ``ast:source-body`` via ``axm.hooks`` entry point.

Designed for protocol agents that need to ``Edit`` a symbol directly from
the briefing without a preceding ``Read``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm.hooks.base import HookResult

logger = logging.getLogger(__name__)

__all__ = ["SourceBodyHook"]


def _read_body(file_path: Path, start: int, end: int) -> str:
    """Read source lines *start* to *end* (1-indexed, inclusive)."""
    lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
    return "".join(lines[start - 1 : end])


def _extract_symbol(
    pkg: Any,
    symbol_name: str,
    pkg_root: Path,
) -> dict[str, Any]:
    """Look up *symbol_name* in *pkg* and return its body dict."""
    from axm_ast.core.analyzer import find_module_for_symbol, search_symbols

    matches = search_symbols(
        pkg, name=symbol_name, returns=None, kind=None, inherits=None
    )
    # Exact-name filter (search_symbols does substring match).
    exact = [m for m in matches if m.name == symbol_name]
    if not exact:
        return {
            "symbol": symbol_name,
            "body": None,
            "error": f"Symbol '{symbol_name}' not found",
        }

    sym = exact[0]
    mod = find_module_for_symbol(pkg, sym)
    if mod is None:
        return {
            "symbol": symbol_name,
            "body": None,
            "error": f"Module not found for '{symbol_name}'",
        }

    if mod.path.is_relative_to(pkg_root):
        rel_path = mod.path.relative_to(pkg_root)
    else:
        rel_path = mod.path
    body = _read_body(mod.path, sym.line_start, sym.line_end)

    return {
        "symbol": symbol_name,
        "file": str(rel_path),
        "start_line": sym.line_start,
        "end_line": sym.line_end,
        "body": body,
    }


@dataclass
class SourceBodyHook:
    """Extract the full source body of one or more symbols.

    Reads ``path`` from *params* (or ``working_dir`` from context)
    and ``symbol`` from *params*.  When *symbol* contains newline
    characters, each line is processed independently.
    """

    def execute(self, context: dict[str, Any], **params: Any) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary.
            **params: Must include ``symbol`` (name(s) to extract).
                Optional ``path`` (overrides ``working_dir`` from context).

        Returns:
            HookResult with ``symbols`` list in metadata on success.
        """
        symbol = params.get("symbol")
        if not symbol:
            return HookResult.fail("Missing required param 'symbol'")

        path = params.get("path") or context.get("working_dir", ".")
        working_dir = Path(path).resolve()
        if not working_dir.is_dir():
            return HookResult.fail(f"working_dir not a directory: {working_dir}")

        try:
            from axm_ast.core.analyzer import analyze_package

            pkg = analyze_package(working_dir)
            symbols = [s.strip() for s in symbol.splitlines() if s.strip()]

            results = [_extract_symbol(pkg, sym, working_dir) for sym in symbols]

            if len(results) == 1:
                return HookResult.ok(symbols=results[0])
            return HookResult.ok(symbols=results)
        except Exception as exc:  # noqa: BLE001
            return HookResult.fail(f"Source body extraction failed: {exc}")
