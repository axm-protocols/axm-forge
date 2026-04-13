"""SearchTool — semantic symbol search."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, ClassVar

from axm.tools.base import AXMTool, ToolResult

logger = logging.getLogger(__name__)

__all__ = ["SearchTool"]


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
        text = SearchTool._render_text(
            symbols,
            name=name,
            returns=returns,
            kind=kind,
            inherits=inherits,
        )
        return ToolResult(
            success=True,
            data={"results": symbols},
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
        name: str | None,
        returns: str | None,
        kind: Any,
        inherits: str | None,
        count: int,
    ) -> str:
        """Build the header line for text rendering."""
        filters: list[str] = []
        if name is not None:
            filters.append(f'name~"{name}"')
        if returns is not None:
            filters.append(f"returns={returns}")
        kind_str = (
            kind
            if isinstance(kind, str)
            else (kind.value if kind is not None else None)
        )
        if kind_str is not None:
            filters.append(f"kind={kind_str}")
        if inherits is not None:
            filters.append(f"inherits={inherits}")
        parts = ["ast_search"]
        if filters:
            parts.append(" · ".join(filters))
        parts.append(f"{count} hits")
        return " | ".join(parts)

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
        name: str | None,
        returns: str | None,
        kind: Any,
        inherits: str | None,
    ) -> str:
        """Group symbols by kind and render as compact text."""
        header = SearchTool._format_text_header(
            name=name,
            returns=returns,
            kind=kind,
            inherits=inherits,
            count=len(symbols),
        )
        if not symbols:
            return header

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
