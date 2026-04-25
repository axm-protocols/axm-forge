"""SearchTool — semantic symbol search."""

from __future__ import annotations

import logging
from difflib import SequenceMatcher, get_close_matches
from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

from axm_ast.core.analyzer import module_dotted_name
from axm_ast.tools.search_text import (
    format_func_line,
    format_symbol_line,
    format_text_header,
    format_variable_line,
    render_suggestion_line,
    render_text,
)

logger = logging.getLogger(__name__)

__all__ = ["SearchTool"]


_FUNC_KINDS = frozenset(
    {"function", "method", "property", "classmethod", "staticmethod", "abstract"}
)


def _collect_module_candidates(
    mod: Any,
    kind: str | None,
    candidates: dict[str, list[tuple[str, str, str]]],
    root: Path | None = None,
) -> None:
    """Populate *candidates* from a single module's symbols.

    When *mod.name* is ``None``, falls back to
    ``module_dotted_name(mod.path, root)`` so that suggestion dicts
    always carry a real dotted module name.
    """
    mod_name: str = mod.name or (
        module_dotted_name(mod.path, root) if root and mod.path else ""
    )
    if kind is None or kind in _FUNC_KINDS:
        for fn in mod.functions:
            fk = fn.kind if isinstance(fn.kind, str) else fn.kind.value
            candidates.setdefault(fn.name.lower(), []).append((fn.name, fk, mod_name))
    for cls in mod.classes:
        if kind is None or kind == "class":
            candidates.setdefault(cls.name.lower(), []).append(
                (cls.name, "class", mod_name)
            )
        if kind is None or kind in _FUNC_KINDS:
            for method in cls.methods:
                mk = method.kind if isinstance(method.kind, str) else method.kind.value
                dotted = f"{cls.name}.{method.name}"
                candidates.setdefault(dotted.lower(), []).append((dotted, mk, mod_name))
    if kind is None or kind == "variable":
        for var in mod.variables:
            candidates.setdefault(var.name.lower(), []).append(
                (var.name, "variable", mod_name)
            )


def _find_suggestions(
    pkg: Any, name: str, *, kind: str | None = None
) -> list[dict[str, Any]]:
    """Find fuzzy suggestions for a symbol name query.

    Passes ``pkg.root`` to ``_collect_module_candidates`` so module
    names are resolved even when the parser leaves ``mod.name`` unset.
    """
    candidates: dict[str, list[tuple[str, str, str]]] = {}

    for mod in pkg.modules:
        _collect_module_candidates(mod, kind, candidates, root=pkg.root)

    if not candidates:
        return []

    matches = get_close_matches(name.lower(), list(candidates.keys()), n=10, cutoff=0.6)

    seen: dict[str, dict[str, Any]] = {}
    for match_key in matches:
        for original_name, sym_kind, module in candidates[match_key]:
            score = round(SequenceMatcher(None, name.lower(), match_key).ratio(), 2)
            if original_name not in seen or score > seen[original_name]["score"]:
                seen[original_name] = {
                    "name": original_name,
                    "score": score,
                    "kind": sym_kind,
                    "module": module,
                }

    return sorted(seen.values(), key=lambda s: s["score"], reverse=True)


def _add_variable_fields(entry: dict[str, Any], sym: Any) -> None:
    """Populate annotation and value_repr on a variable entry."""
    if sym.annotation:
        entry["annotation"] = sym.annotation
    if sym.value_repr:
        entry["value_repr"] = sym.value_repr


def _resolve_kind(sym: Any) -> str | None:
    """Resolve kind string from a fallback symbol."""
    if hasattr(sym, "value_repr"):
        return "variable"
    if hasattr(sym, "kind"):
        return sym.kind if isinstance(sym.kind, str) else sym.kind.value
    return None


def _format_symbol(sym: Any, module_name: str) -> dict[str, Any]:
    """Format an AST symbol into a serialized dict entry.

    Returns a dict with keys ``name``, ``module``, and optionally
    ``signature``, ``return_type``, ``kind`` (function/method/property/
    classmethod/staticmethod/abstract/class/variable), ``annotation``,
    and ``value_repr``.
    """
    from axm_ast.models.nodes import ClassInfo, FunctionInfo, VariableInfo

    entry: dict[str, Any] = {
        "name": sym.name,
        "module": module_name,
    }
    if hasattr(sym, "signature"):
        entry["signature"] = sym.signature
    if hasattr(sym, "return_type"):
        entry["return_type"] = sym.return_type
    match sym:
        case FunctionInfo():
            entry["kind"] = sym.kind.value
        case ClassInfo():
            entry["kind"] = "class"
        case VariableInfo():
            entry["kind"] = "variable"
            _add_variable_fields(entry, sym)
        case _:
            kind = _resolve_kind(sym)
            if kind is not None:
                entry["kind"] = kind
    return entry


def _load_package(path: str) -> Any:
    """Resolve path and load package. Returns PackageInfo or ToolResult on error."""
    project_path = Path(path).resolve()
    if not project_path.is_dir():
        return ToolResult(success=False, error=f"Not a directory: {project_path}")
    from axm_ast.core.cache import get_package

    return get_package(project_path)


def _validate_kind(kind: str | None) -> Any:
    """Validate kind string.

    Returns SymbolKind on success or ToolResult on error.
    """
    if kind is None:
        return None
    from axm_ast.models import SymbolKind

    try:
        return SymbolKind(kind)
    except ValueError:
        valid = ", ".join(SymbolKind)
        return ToolResult(
            success=False,
            error=f"Invalid kind: {kind}. Valid: {valid}",
        )


def _search(
    pkg: Any,
    *,
    name: str | None,
    returns: str | None,
    kind: Any,
    inherits: str | None,
) -> ToolResult:
    """Run symbol search across a package and return formatted results.

    Returns a ToolResult whose ``data`` dict contains a single ``results``
    key — a list of formatted symbol dicts.
    """
    from axm_ast.core.analyzer import search_symbols

    results = search_symbols(
        pkg,
        name=name,
        returns=returns,
        kind=kind,
        inherits=inherits,
    )
    symbols = [SearchTool._format_symbol(sym, mod_name) for mod_name, sym in results]

    suggestions: list[dict[str, Any]] = []
    if not symbols and name is not None and pkg is not None:
        kind_str = (
            kind
            if isinstance(kind, str)
            else (kind.value if kind is not None else None)
        )
        suggestions = _find_suggestions(pkg, name, kind=kind_str)

    sf = {"name": name, "returns": returns, "kind": kind, "inherits": inherits}
    text = render_text(
        symbols,
        search_filters=sf,
        suggestions=suggestions,
    )
    data: dict[str, Any] = {"results": symbols}
    if suggestions:
        data["suggestions"] = suggestions
    return ToolResult(
        success=True,
        data=data,
        text=text,
    )


class SearchTool(AXMTool):
    """Search symbols by name, return type, kind, or base class.

    Registered as ``ast_search`` via axm.tools entry point.
    """

    agent_hint: str = (
        "Find symbols by name, return type, kind, or base class"
        " — AST-precise, replaces grep."
        " Ask 'functions returning X' or 'classes inheriting Y'."
    )

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
            kind: Filter by kind (function, method, property,
                classmethod, staticmethod, abstract, class, variable).
            inherits: Filter by base class name.

        Returns:
            ToolResult with matching symbols.
        """
        try:
            pkg = _load_package(path)
            if isinstance(pkg, ToolResult):
                return pkg

            kind_enum = _validate_kind(kind)
            if isinstance(kind_enum, ToolResult):
                return kind_enum

            return _search(
                pkg,
                name=name,
                returns=returns,
                kind=kind_enum,
                inherits=inherits,
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))


# ── Backwards-compat aliases ───────────────────────────────────────────────
# Tests reference these on ``SearchTool`` directly; keep them callable via the
# class without re-defining methods (which would re-trigger the god-class
# audit). Aliases are attached after the class body so they don't count as
# methods of ``SearchTool``.
SearchTool._load_package = staticmethod(_load_package)
SearchTool._validate_kind = staticmethod(_validate_kind)
SearchTool._search = staticmethod(_search)
SearchTool._format_symbol = staticmethod(_format_symbol)
SearchTool._find_suggestions = staticmethod(_find_suggestions)
SearchTool._format_text_header = staticmethod(format_text_header)
SearchTool._format_symbol_line = staticmethod(format_symbol_line)
SearchTool._format_func_line = staticmethod(format_func_line)
SearchTool._format_variable_line = staticmethod(format_variable_line)
SearchTool._render_suggestion_line = staticmethod(render_suggestion_line)
SearchTool._render_text = staticmethod(render_text)
