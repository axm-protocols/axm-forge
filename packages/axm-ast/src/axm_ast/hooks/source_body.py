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


def _not_found(symbol_name: str) -> dict[str, Any]:
    """Return a not-found result dict."""
    return {
        "symbol": symbol_name,
        "body": None,
        "error": f"Symbol '{symbol_name}' not found",
    }


def _build_body(sym: Any, mod: Any, symbol_name: str, pkg_root: Path) -> dict[str, Any]:
    """Build a body result dict from a resolved symbol and module."""
    from axm_ast.models.nodes import VariableInfo

    rel = (
        mod.path.relative_to(pkg_root)
        if mod.path.is_relative_to(pkg_root)
        else mod.path
    )
    if isinstance(sym, VariableInfo):
        body = _read_body(mod.path, sym.line, sym.line)
        return {
            "symbol": symbol_name,
            "file": str(rel),
            "start_line": sym.line,
            "end_line": sym.line,
            "value_repr": sym.value_repr,
            "body": body,
        }
    body = _read_body(mod.path, sym.line_start, sym.line_end)
    return {
        "symbol": symbol_name,
        "file": str(rel),
        "start_line": sym.line_start,
        "end_line": sym.line_end,
        "body": body,
    }


def _resolve_dotted(
    pkg: Any,
    symbol_name: str,
    pkg_root: Path,
) -> dict[str, Any] | None:
    """Resolve a dotted symbol like ``ClassName.method`` or ``module.func``.

    Returns a body dict on success, or *None* if no resolution matched
    (so the caller can fall back to flat search).
    """
    from axm_ast.core.analyzer import find_module_for_symbol, search_symbols

    parts = symbol_name.split(".")
    class_name = parts[0]
    member_name = parts[-1]

    # --- Try ClassName.method ---
    classes = search_symbols(
        pkg, name=class_name, returns=None, kind=None, inherits=None
    )
    cls = next(
        (c for c in classes if hasattr(c, "methods") and c.name == class_name),
        None,
    )
    if cls is not None:
        method = next((m for m in cls.methods if m.name == member_name), None)
        if method is not None:
            mod = find_module_for_symbol(pkg, cls)
            if mod is not None:
                rel = (
                    mod.path.relative_to(pkg_root)
                    if mod.path.is_relative_to(pkg_root)
                    else mod.path
                )
                body = _read_body(mod.path, method.line_start, method.line_end)
                return {
                    "symbol": symbol_name,
                    "file": str(rel),
                    "start_line": method.line_start,
                    "end_line": method.line_end,
                    "body": body,
                }
        # Class found but member missing → definitive not-found.
        return {
            "symbol": symbol_name,
            "body": None,
            "error": f"Symbol '{symbol_name}' not found",
        }

    # --- Try module.symbol ---
    mods = pkg.modules
    if isinstance(mods, dict):
        name_to_mod = mods
    else:
        name_to_mod = dict(zip(pkg.module_names, mods, strict=True))
    for split_at in range(len(parts) - 1, 0, -1):
        mod_prefix = ".".join(parts[:split_at])
        sym_name = ".".join(parts[split_at:])
        if name_to_mod.get(mod_prefix) is None:
            continue
        # Module prefix matched — resolve the symbol part via search.
        matches = search_symbols(
            pkg, name=sym_name, returns=None, kind=None, inherits=None
        )
        exact = [m for m in matches if m.name == sym_name]
        if not exact:
            return _not_found(symbol_name)
        sym = exact[0]
        mod = find_module_for_symbol(pkg, sym)
        if mod is None:
            return _not_found(symbol_name)
        return _build_body(sym, mod, symbol_name, pkg_root)

    return None


def _extract_symbol(
    pkg: Any,
    symbol_name: str,
    pkg_root: Path,
) -> dict[str, Any]:
    """Look up *symbol_name* in *pkg* and return its body dict."""
    from axm_ast.core.analyzer import find_module_for_symbol, search_symbols
    from axm_ast.models.nodes import VariableInfo

    # Dotted name resolution (e.g. "ClassName.method" or "module.func").
    if "." in symbol_name:
        result = _resolve_dotted(pkg, symbol_name, pkg_root)
        if result is not None:
            return result

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

    # VariableInfo has a single `line`, not line_start/line_end.
    if isinstance(sym, VariableInfo):
        body = _read_body(mod.path, sym.line, sym.line)
        return {
            "symbol": symbol_name,
            "file": str(rel_path),
            "start_line": sym.line,
            "end_line": sym.line,
            "value_repr": sym.value_repr,
            "body": body,
        }

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
