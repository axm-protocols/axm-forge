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
from typing import NotRequired, TypedDict

from axm.hooks.base import HookResult

from axm_ast.core.analyzer import (
    analyze_package,
    find_module_for_symbol,
    search_symbols,
)
from axm_ast.models.nodes import (
    ClassInfo,
    FunctionInfo,
    ModuleInfo,
    PackageInfo,
    VariableInfo,
)

logger = logging.getLogger(__name__)

__all__ = ["SourceBodyHook"]


class _SymbolEntry(TypedDict):
    """Result entry for one symbol extraction (success or not-found).

    On success ``body`` is a non-empty string and ``file``/``start_line``/
    ``end_line`` are populated; on failure ``body`` is ``None`` and
    ``error`` is set instead. ``value_repr`` is only present for
    module-level variables.
    """

    symbol: str
    body: str | None
    file: NotRequired[str]
    start_line: NotRequired[int]
    end_line: NotRequired[int]
    value_repr: NotRequired[str | None]
    error: NotRequired[str]


def _read_body(file_path: Path, start: int, end: int) -> str:
    """Read source lines *start* to *end* (1-indexed, inclusive)."""
    lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
    return "".join(lines[start - 1 : end])


def _not_found(symbol_name: str) -> _SymbolEntry:
    """Return a not-found result dict."""
    return {
        "symbol": symbol_name,
        "body": None,
        "error": f"Symbol '{symbol_name}' not found",
    }


def _build_body(
    sym: FunctionInfo | ClassInfo | VariableInfo,
    mod: ModuleInfo,
    symbol_name: str,
    pkg_root: Path,
) -> _SymbolEntry:
    """Build a body result dict from a resolved symbol and module."""
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


def _build_method_body(
    pkg: PackageInfo,
    cls: ClassInfo,
    method: FunctionInfo,
    symbol_name: str,
    pkg_root: Path,
) -> _SymbolEntry | None:
    """Build body dict for a resolved class method."""
    mod = find_module_for_symbol(pkg, cls)
    if mod is None:
        return None
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


def _resolve_as_class_method(
    pkg: PackageInfo,
    class_name: str,
    member_name: str,
    symbol_name: str,
    pkg_root: Path,
) -> _SymbolEntry | None:
    """Try ``ClassName.method`` resolution.

    Returns body dict on success, not-found dict if the class exists
    but the member is missing, or *None* if no class matched.
    """
    classes = search_symbols(
        pkg, name=class_name, returns=None, kind=None, inherits=None
    )
    cls = next(
        (
            c
            for _, c in classes
            if isinstance(c, ClassInfo) and c.name == class_name
        ),
        None,
    )
    if cls is None:
        return None
    method = next((m for m in cls.methods if m.name == member_name), None)
    if method is None:
        return _not_found(symbol_name)
    result = _build_method_body(pkg, cls, method, symbol_name, pkg_root)
    if result is not None:
        return result
    # Class found but member missing → definitive not-found.
    return _not_found(symbol_name)


def _resolve_as_nested_class(
    pkg: PackageInfo,
    parts: list[str],
    symbol_name: str,
    pkg_root: Path,
) -> _SymbolEntry | None:
    """Resolve ``Outer.Inner.method`` via outermost class + innermost member."""
    return _resolve_as_class_method(pkg, parts[0], parts[-1], symbol_name, pkg_root)


def _get_module_map(pkg: PackageInfo) -> dict[str, ModuleInfo]:
    """Build a name → module mapping from a package."""
    mods = pkg.modules
    return dict(zip(pkg.module_names, mods, strict=True))


def _resolve_as_module_symbol(
    pkg: PackageInfo,
    parts: list[str],
    symbol_name: str,
    pkg_root: Path,
) -> _SymbolEntry | None:
    """Try ``module.symbol`` resolution with longest-prefix matching."""
    from axm_ast.core.analyzer import find_module_for_symbol, search_symbols

    name_to_mod = _get_module_map(pkg)
    for split_at in range(len(parts) - 1, 0, -1):
        mod_prefix = ".".join(parts[:split_at])
        sym_name = ".".join(parts[split_at:])
        if name_to_mod.get(mod_prefix) is None:
            continue
        matches = search_symbols(
            pkg, name=sym_name, returns=None, kind=None, inherits=None
        )
        exact = [m for _, m in matches if m.name == sym_name]
        if not exact:
            return _not_found(symbol_name)
        sym = exact[0]
        mod = find_module_for_symbol(pkg, sym)
        if mod is None:
            return _not_found(symbol_name)
        return _build_body(sym, mod, symbol_name, pkg_root)
    return None


def _validate_source_body_params(
    context: dict[str, object],
    params: dict[str, object],
) -> tuple[str | None, Path | None, str | None]:
    """Extract and validate params for source-body extraction."""
    raw_symbol = params.get("symbol")
    if not raw_symbol:
        return None, None, "Missing required param 'symbol'"
    if not isinstance(raw_symbol, str):
        return None, None, (f"symbol must be str, got {type(raw_symbol).__name__}")
    raw_path = params.get("path") or context.get("working_dir", ".")
    if not isinstance(raw_path, (str, Path)):
        return None, None, (f"path must be str or Path, got {type(raw_path).__name__}")
    working_dir = Path(raw_path).resolve()
    if not working_dir.is_dir():
        return None, None, f"working_dir not a directory: {working_dir}"
    return raw_symbol, working_dir, None


def _resolve_dotted(
    pkg: PackageInfo,
    symbol_name: str,
    pkg_root: Path,
) -> _SymbolEntry | None:
    """Resolve a dotted symbol like ``ClassName.method`` or ``module.func``.

    Returns a body dict on success, or *None* if no resolution matched
    (so the caller can fall back to flat search).
    """
    _max_dotted_parts = 2
    parts = symbol_name.split(".")
    if len(parts) > _max_dotted_parts:
        result = _resolve_as_nested_class(pkg, parts, symbol_name, pkg_root)
    else:
        result = _resolve_as_class_method(
            pkg,
            parts[0],
            parts[-1],
            symbol_name,
            pkg_root,
        )
    if result is not None:
        return result
    return _resolve_as_module_symbol(pkg, parts, symbol_name, pkg_root)


def _extract_symbol(
    pkg: PackageInfo,
    symbol_name: str,
    pkg_root: Path,
) -> _SymbolEntry:
    """Look up *symbol_name* in *pkg* and return its body dict."""

    # Dotted name resolution (e.g. "ClassName.method" or "module.func").
    if "." in symbol_name:
        result = _resolve_dotted(pkg, symbol_name, pkg_root)
        if result is not None:
            return result

    matches = search_symbols(
        pkg, name=symbol_name, returns=None, kind=None, inherits=None
    )
    # Exact-name filter (search_symbols does substring match).
    exact = [m for _, m in matches if m.name == symbol_name]
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


def _format_as_markdown(
    results: list[_SymbolEntry],
    working_dir: Path,
) -> str:
    """Format extraction results as grouped markdown.

    Groups symbol bodies by file path and renders each group as
    a fenced python code block preceded by the relative file path.
    """
    from collections import OrderedDict

    grouped: OrderedDict[str, list[str]] = OrderedDict()
    for entry in results:
        body = entry.get("body")
        if body is None:
            # Symbol not found — include error as comment
            err = entry.get("error", "unknown error")
            snippet = f"# {entry.get('symbol', '?')}: {err}"
        else:
            snippet = body
            if entry.get("value_repr") is not None:
                snippet += f"  # value_repr: {entry['value_repr']}"
        file_key = entry.get("file", "<unknown>")
        grouped.setdefault(file_key, []).append(snippet)

    parts: list[str] = []
    for filepath, bodies in grouped.items():
        parts.append(filepath)
        parts.append("```python")
        parts.append("\n\n".join(bodies))
        parts.append("```")

    return "\n".join(parts)


def _dedup_symbols(symbols: list[str]) -> list[str]:
    """Remove dotted symbols whose parent class is already in the list.

    When both ``Foo`` and ``Foo.method`` appear, the method body is already
    included in the class body — extracting it separately wastes tokens.
    """
    bare: set[str] = {s for s in symbols if "." not in s}
    seen: dict[str, None] = {}
    for s in symbols:
        if "." in s and s.split(".", 1)[0] in bare:
            key = s.split(".", 1)[0]
        else:
            key = s
        if key not in seen:
            seen[key] = None
    return list(seen)


def _run_extraction(symbol: str, working_dir: Path) -> HookResult:
    """Run symbol extraction and return a HookResult."""
    pkg = analyze_package(working_dir)
    symbols = _dedup_symbols([s.strip() for s in symbol.splitlines() if s.strip()])
    results = [_extract_symbol(pkg, sym, working_dir) for sym in symbols]
    file_list = list(
        dict.fromkeys(entry["file"] for entry in results if entry.get("file"))
    )
    formatted = _format_as_markdown(results, working_dir)
    return HookResult.ok(symbols=formatted, files=file_list)


@dataclass
class SourceBodyHook:
    """Extract the full source body of one or more symbols.

    Reads ``path`` from *params* (or ``working_dir`` from context)
    and ``symbol`` from *params*.  When *symbol* contains newline
    characters, each line is processed independently.
    """

    def execute(self, context: dict[str, object], **params: object) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary.
            **params: Must include ``symbol`` (name(s) to extract).
                Optional ``path`` (overrides ``working_dir`` from context).

        Returns:
            HookResult with ``symbols`` list in metadata on success.
        """
        symbol, working_dir, error = _validate_source_body_params(
            context,
            params,
        )
        if error:
            return HookResult.fail(error)
        assert symbol is not None
        assert working_dir is not None

        try:
            return _run_extraction(symbol, working_dir)
        except Exception as exc:  # noqa: BLE001
            return HookResult.fail(f"Source body extraction failed: {exc}")
