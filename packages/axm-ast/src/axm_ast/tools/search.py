"""SearchTool — semantic symbol search."""

from __future__ import annotations

import dataclasses
import logging
from difflib import SequenceMatcher, get_close_matches
from pathlib import Path
from typing import Any, ClassVar

from axm.tools.base import AXMTool, ToolResult

logger = logging.getLogger(__name__)

__all__ = ["SearchTool"]


_FUNC_KINDS = frozenset(
    {"function", "method", "property", "classmethod", "staticmethod", "abstract"}
)

_KIND_ABBREV_LEN = 4


@dataclasses.dataclass(frozen=True, slots=True)
class _SearchFilters:
    """Bundled filter parameters for search rendering."""

    name: str | None
    returns: str | None
    kind: Any
    inherits: str | None


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
            pkg = self._load_package(path)
            if isinstance(pkg, ToolResult):
                return pkg

            kind_enum = self._validate_kind(kind)
            if isinstance(kind_enum, ToolResult):
                return kind_enum

            return self._search(
                pkg,
                name=name,
                returns=returns,
                kind=kind_enum,
                inherits=inherits,
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

    @staticmethod
    def _load_package(path: str) -> Any:
        """Resolve path and load package. Returns PackageInfo or ToolResult on error."""
        project_path = Path(path).resolve()
        if not project_path.is_dir():
            return ToolResult(success=False, error=f"Not a directory: {project_path}")
        from axm_ast.core.cache import get_package

        return get_package(project_path)

    @staticmethod
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
        symbols = [
            SearchTool._format_symbol(sym, mod_name) for mod_name, sym in results
        ]

        suggestions: list[dict[str, Any]] = []
        if not symbols and name is not None and pkg is not None:
            kind_str = (
                kind
                if isinstance(kind, str)
                else (kind.value if kind is not None else None)
            )
            suggestions = _find_suggestions(pkg, name, kind=kind_str)

        sf = {"name": name, "returns": returns, "kind": kind, "inherits": inherits}
        text = SearchTool._render_text(
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

    def _validate_kind(self, kind: str | None) -> Any:
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

    @staticmethod
    def _format_text_header(
        *,
        search_filters: dict[str, Any],
        count: int,
        suggestion_count: int = 0,
    ) -> str:
        """Build the header line for text rendering."""
        name = search_filters.get("name")
        returns = search_filters.get("returns")
        kind = search_filters.get("kind")
        inherits = search_filters.get("inherits")
        parts: list[str] = []
        if name is not None:
            parts.append(f'name~"{name}"')
        if returns is not None:
            parts.append(f"returns={returns}")
        kind_str = (
            kind
            if isinstance(kind, str)
            else (kind.value if kind is not None else None)
        )
        if kind_str is not None:
            parts.append(f"kind={kind_str}")
        if inherits is not None:
            parts.append(f"inherits={inherits}")
        sections = ["ast_search"]
        if parts:
            sections.append(" · ".join(parts))
        hits_part = f"{count} hits"
        if suggestion_count > 0:
            hits_part += f" · {suggestion_count} suggestions"
        sections.append(hits_part)
        return " | ".join(sections)

    _FUNC_KINDS: ClassVar[set[str]] = {
        "function",
        "method",
        "property",
        "classmethod",
        "staticmethod",
        "abstract",
    }

    @staticmethod
    def _extract_params_block(sig: str) -> str:
        """Extract the parenthesised params block from a signature string."""
        paren_start = sig.find("(")
        if paren_start == -1:
            return "()"
        rest = sig[paren_start:]
        depth = 0
        for i, ch in enumerate(rest):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return rest[: i + 1]
        return rest

    @staticmethod
    def _format_func_line(sym: dict[str, Any]) -> str:
        """Format a function-like symbol as a compact text line."""
        params = SearchTool._extract_params_block(sym.get("signature", ""))
        line = f"{sym['name']}{params}"
        ret = sym.get("return_type")
        if ret is not None:
            line += f" -> {ret}"
        return line

    @staticmethod
    def _format_variable_line(sym: dict[str, Any]) -> str:
        """Format a variable symbol as a compact text line."""
        name = sym["name"]
        ann = sym.get("annotation")
        val = sym.get("value_repr")
        if ann and val:
            return f"{name}: {ann} = {val}"
        if ann:
            return f"{name}: {ann}"
        if val:
            return f"{name} = {val}"
        return str(name)

    @staticmethod
    def _format_symbol_line(sym: dict[str, Any]) -> str:
        """Render one symbol dict as a compact text line."""
        kind = sym.get("kind", "")
        if kind in SearchTool._FUNC_KINDS:
            return SearchTool._format_func_line(sym)
        if kind == "class":
            return str(sym["name"])
        return SearchTool._format_variable_line(sym)

    @staticmethod
    def _collect_module_candidates(
        mod: Any,
        kind: str | None,
        candidates: dict[str, list[tuple[str, str, str]]],
    ) -> None:
        """Populate *candidates* from a single module's symbols."""
        mod_name = mod.name
        if kind is None or kind in _FUNC_KINDS:
            for fn in mod.functions:
                fk = fn.kind if isinstance(fn.kind, str) else fn.kind.value
                candidates.setdefault(fn.name.lower(), []).append(
                    (fn.name, fk, mod_name)
                )
        for cls in mod.classes:
            if kind is None or kind == "class":
                candidates.setdefault(cls.name.lower(), []).append(
                    (cls.name, "class", mod_name)
                )
            if kind is None or kind in _FUNC_KINDS:
                for method in cls.methods:
                    mk = (
                        method.kind
                        if isinstance(method.kind, str)
                        else method.kind.value
                    )
                    dotted = f"{cls.name}.{method.name}"
                    candidates.setdefault(dotted.lower(), []).append(
                        (dotted, mk, mod_name)
                    )
        if kind is None or kind == "variable":
            for var in mod.variables:
                candidates.setdefault(var.name.lower(), []).append(
                    (var.name, "variable", mod_name)
                )

    @staticmethod
    def _find_suggestions(
        pkg: Any, name: str, *, kind: str | None = None
    ) -> list[dict[str, Any]]:
        """Find fuzzy suggestions for a symbol name query."""
        candidates: dict[str, list[tuple[str, str, str]]] = {}

        for mod in pkg.modules:
            SearchTool._collect_module_candidates(mod, kind, candidates)

        if not candidates:
            return []

        matches = get_close_matches(
            name.lower(), list(candidates.keys()), n=10, cutoff=0.6
        )

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

    @staticmethod
    def _render_suggestion_line(suggestion: dict[str, Any]) -> str:
        """Render one suggestion as a compact ``?``-prefixed text line."""
        name = suggestion["name"]
        score = (
            f".{int(suggestion['score'] * 100):02d}"
            if suggestion["score"] < 1
            else "1.0"
        )
        kind = (
            suggestion["kind"][:_KIND_ABBREV_LEN]
            if len(suggestion["kind"]) > _KIND_ABBREV_LEN
            else suggestion["kind"]
        )
        module = suggestion["module"]
        return f"? {name:<22} {score}  {kind:<6} {module}"

    @staticmethod
    def _group_symbols(
        symbols: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        """Partition symbols into (funcs, classes, variables)."""
        funcs: list[dict[str, Any]] = []
        classes: list[dict[str, Any]] = []
        variables: list[dict[str, Any]] = []
        for s in symbols:
            k = s.get("kind", "")
            if k in SearchTool._FUNC_KINDS:
                funcs.append(s)
            elif k == "class":
                classes.append(s)
            else:
                variables.append(s)
        return funcs, classes, variables

    @staticmethod
    def _render_text(
        symbols: list[dict[str, Any]],
        *,
        search_filters: dict[str, Any],
        suggestions: list[dict[str, Any]] | None = None,
    ) -> str:
        """Group symbols by kind and render as compact text."""
        suggestions = suggestions or []
        header = SearchTool._format_text_header(
            search_filters=search_filters,
            count=len(symbols),
            suggestion_count=len(suggestions),
        )
        if not symbols and not suggestions:
            return header

        if not symbols and suggestions:
            lines = [header]
            lines.extend(SearchTool._render_suggestion_line(s) for s in suggestions)
            return "\n".join(lines)

        funcs, classes, variables = SearchTool._group_symbols(symbols)
        fmt = SearchTool._format_symbol_line
        lines = [header]
        lines.extend(fmt(s) for s in funcs)
        if classes:
            lines.append(", ".join(fmt(s) for s in classes))
        lines.extend(fmt(s) for s in variables)
        return "\n".join(lines)

    @staticmethod
    def _add_variable_fields(entry: dict[str, Any], sym: Any) -> None:
        """Populate annotation and value_repr on a variable entry."""
        if sym.annotation:
            entry["annotation"] = sym.annotation
        if sym.value_repr:
            entry["value_repr"] = sym.value_repr

    @staticmethod
    def _resolve_kind(sym: Any) -> str | None:
        """Resolve kind string from a fallback symbol."""
        if hasattr(sym, "value_repr"):
            return "variable"
        if hasattr(sym, "kind"):
            return sym.kind if isinstance(sym.kind, str) else sym.kind.value
        return None

    @staticmethod
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
                SearchTool._add_variable_fields(entry, sym)
            case _:
                kind = SearchTool._resolve_kind(sym)
                if kind is not None:
                    entry["kind"] = kind
        return entry


_find_suggestions = SearchTool._find_suggestions
