"""InspectTool — inspect a single symbol by name."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

from axm_ast.models.nodes import (
    ClassInfo,
    FunctionInfo,
    ModuleInfo,
    PackageInfo,
    VariableInfo,
)

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

        source = bool(kwargs.get("source", False))

        try:
            project_path = self._resolve_path(path)
            if isinstance(project_path, ToolResult):
                return project_path

            if symbols is not None:
                return self._inspect_batch(project_path, symbols, source=source)

            return self._inspect_symbol(project_path, symbol, source=source)  # type: ignore[arg-type]
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

    @staticmethod
    def _resolve_path(path: str) -> Path | ToolResult:
        """Resolve and validate project path."""
        project_path = Path(path).resolve()
        if not project_path.is_dir():
            return ToolResult(success=False, error=f"Not a directory: {project_path}")
        return project_path

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
        return ToolResult(success=True, data={"symbols": results})

    def _inspect_symbol(
        self, project_path: Path, symbol: str, *, source: bool = False
    ) -> ToolResult:
        """Core symbol inspection logic."""
        from axm_ast.core.analyzer import search_symbols
        from axm_ast.core.cache import get_package

        pkg = get_package(project_path)

        if "." in symbol:
            return self._inspect_dotted(pkg, symbol, source=source)

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
            mod_result = self._inspect_module(pkg, symbol)
            if mod_result is not None:
                return mod_result
            return ToolResult(
                success=False,
                error=f"Symbol '{symbol}' not found",
            )

        sym = results[0]
        file_path = self._find_symbol_file(pkg, sym)
        abs_path = self._find_symbol_abs_path(pkg, sym)
        return ToolResult(
            success=True,
            data={
                "symbol": self._build_detail(
                    sym, file=file_path, abs_path=abs_path, source=source
                )
            },
        )

    def _inspect_dotted(
        self, pkg: PackageInfo, symbol: str, *, source: bool = False
    ) -> ToolResult:
        """Resolve a dotted symbol (module, module.symbol, or Class.method)."""
        # Check module name first (e.g. "sub.helpers" is a module)
        result = self._inspect_module(pkg, symbol)
        if result is not None:
            return result

        result = self._resolve_module_symbol(pkg, symbol, source=source)
        if result is not None:
            return result

        result = self._resolve_class_method(pkg, symbol, source=source)
        if result is not None:
            return result

        return ToolResult(
            success=False,
            error=(
                f"Symbol '{symbol}' not found"
                " (tried module name, module.symbol, and Class.method)"
            ),
        )

    def _inspect_module(self, pkg: PackageInfo, name: str) -> ToolResult | None:
        """Try to resolve *name* as a module name and return module metadata."""
        mod = self._resolve_module(pkg, name)
        if mod is None or isinstance(mod, ToolResult):
            return mod

        detail = self._build_module_detail(pkg, mod, name)
        return ToolResult(success=True, data={"symbol": detail})

    def _build_module_detail(
        self, pkg: PackageInfo, mod: ModuleInfo, name: str
    ) -> dict[str, Any]:
        """Build detail dict for a module."""
        return {
            "name": name,
            "kind": "module",
            "file": self._relative_path(pkg, mod.path),
            "docstring": mod.docstring or "",
            "functions": [f.name for f in mod.functions],
            "classes": [c.name for c in mod.classes],
            "symbol_count": len(mod.functions) + len(mod.classes),
        }

    def _resolve_module(
        self,
        pkg: PackageInfo,
        name: str,
    ) -> ModuleInfo | ToolResult | None:
        """Resolve a name to a module via exact or substring match."""
        mod_names = pkg.module_names
        name_to_mod: dict[str, ModuleInfo] = dict(
            zip(mod_names, pkg.modules, strict=True)
        )

        mod = name_to_mod.get(name)
        if mod is not None:
            return mod

        matches = [n for n in mod_names if name in n]
        if len(matches) == 1:
            return name_to_mod[matches[0]]
        if len(matches) > 1:
            return ToolResult(
                success=False,
                error=(
                    f"Multiple modules match '{name}': {', '.join(sorted(matches))}"
                ),
            )
        return None

    def _resolve_module_symbol(
        self, pkg: PackageInfo, dotted: str, *, source: bool = False
    ) -> ToolResult | None:
        """Try to resolve ``dotted`` as ``module_name.symbol_name``.

        Tries longest module prefix first (e.g. ``core.checker`` before ``core``).
        Returns None if no module prefix matches.
        """
        # Build name → module mapping
        mod_names = pkg.module_names
        name_to_mod = dict(zip(mod_names, pkg.modules, strict=True))

        parts = dotted.split(".")
        # Try longest prefix first: for "a.b.c" try "a.b" then "a"
        for split_at in range(len(parts) - 1, 0, -1):
            mod_prefix = ".".join(parts[:split_at])
            sym_name = ".".join(parts[split_at:])
            mod = name_to_mod.get(mod_prefix)
            if mod is None:
                continue
            file_rel = self._relative_path(pkg, mod.path)
            abs_mod = str(mod.path)
            # Found a module — search for the symbol within it
            for fn in mod.functions:
                if fn.name == sym_name:
                    return ToolResult(
                        success=True,
                        data={
                            "symbol": self._build_detail(
                                fn,
                                file=file_rel,
                                abs_path=abs_mod,
                                source=source,
                            )
                        },
                    )
            for cls in mod.classes:
                if cls.name == sym_name:
                    return ToolResult(
                        success=True,
                        data={
                            "symbol": self._build_detail(
                                cls,
                                file=file_rel,
                                abs_path=abs_mod,
                                source=source,
                            )
                        },
                    )
            # Module found but symbol not in it
            return ToolResult(
                success=False,
                error=(f"Symbol '{sym_name}' not found in module '{mod_prefix}'"),
            )
        return None

    def _resolve_class_method(
        self, pkg: PackageInfo, dotted: str, *, source: bool = False
    ) -> ToolResult | None:
        """Try to resolve ``dotted`` as ``ClassName.method_name``.

        Returns None if no class matches.
        """
        from axm_ast.core.analyzer import search_symbols

        parts = dotted.split(".")
        class_name = parts[0]
        method_name = parts[-1]

        classes = search_symbols(
            pkg, name=class_name, returns=None, kind=None, inherits=None
        )
        cls = next(
            (c for c in classes if isinstance(c, ClassInfo) and c.name == class_name),
            None,
        )
        if cls is None:
            return None

        method = next((m for m in cls.methods if m.name == method_name), None)
        if method is None:
            return ToolResult(
                success=False,
                error=(f"Method '{method_name}' not found in class '{class_name}'"),
            )

        file_path = self._find_symbol_file(pkg, cls)
        abs_path = self._find_symbol_abs_path(pkg, cls)
        return ToolResult(
            success=True,
            data={
                "symbol": self._build_detail(
                    method,
                    file=file_path,
                    abs_path=abs_path,
                    source=source,
                )
            },
        )

    @staticmethod
    def _find_symbol_file(
        pkg: PackageInfo, sym: FunctionInfo | ClassInfo | VariableInfo
    ) -> str:
        """Find the relative file path for a symbol within the package."""
        from axm_ast.core.analyzer import find_module_for_symbol

        mod = find_module_for_symbol(pkg, sym)
        if mod is not None:
            return InspectTool._relative_path(pkg, mod.path)
        return ""

    @staticmethod
    def _find_symbol_abs_path(
        pkg: PackageInfo, sym: FunctionInfo | ClassInfo | VariableInfo
    ) -> str:
        """Find the absolute file path for a symbol within the package."""
        from axm_ast.core.analyzer import find_module_for_symbol

        mod = find_module_for_symbol(pkg, sym)
        if mod is not None:
            return str(mod.path)
        return ""

    @staticmethod
    def _relative_path(pkg: PackageInfo, mod_path: Path) -> str:
        """Compute relative path from package root."""
        try:
            return str(mod_path.relative_to(pkg.root.parent))
        except ValueError:
            return str(mod_path)

    @staticmethod
    def _variable_detail(
        sym: VariableInfo,
        *,
        file: str = "",
    ) -> dict[str, Any]:
        """Build detail dict from a VariableInfo."""
        detail: dict[str, Any] = {
            "name": sym.name,
            "file": file,
            "kind": "variable",
            "start_line": sym.line,
            "end_line": sym.line,
            "module": "",
        }
        if sym.annotation is not None:
            detail["annotation"] = sym.annotation
        if sym.value_repr is not None:
            detail["value_repr"] = sym.value_repr
        return detail

    @staticmethod
    def _function_detail(
        sym: FunctionInfo,
        *,
        file: str = "",
    ) -> dict[str, Any]:
        """Build detail dict from a FunctionInfo."""
        detail: dict[str, Any] = {
            "name": sym.name,
            "file": file,
            "start_line": sym.line_start,
            "end_line": sym.line_end,
        }
        if sym.docstring is not None:
            detail["docstring"] = sym.docstring
        detail["signature"] = sym.signature
        if sym.return_type is not None:
            detail["return_type"] = sym.return_type
        if sym.params:
            detail["parameters"] = [
                {"name": p.name, "annotation": p.annotation, "default": p.default}
                for p in sym.params
            ]
        detail["module"] = ""
        return detail

    @staticmethod
    def _class_detail(
        sym: ClassInfo,
        *,
        file: str = "",
    ) -> dict[str, Any]:
        """Build detail dict from a ClassInfo."""
        detail: dict[str, Any] = {
            "name": sym.name,
            "file": file,
            "start_line": sym.line_start,
            "end_line": sym.line_end,
        }
        if sym.docstring is not None:
            detail["docstring"] = sym.docstring
        if sym.bases:
            detail["bases"] = sym.bases
        if sym.methods:
            detail["methods"] = [m.name for m in sym.methods]
        detail["module"] = ""
        return detail

    @staticmethod
    def _build_detail(
        sym: FunctionInfo | ClassInfo | VariableInfo,
        *,
        file: str = "",
        abs_path: str = "",
        source: bool = False,
    ) -> dict[str, Any]:
        """Build detail dict from a FunctionInfo, ClassInfo, or VariableInfo."""
        if isinstance(sym, VariableInfo):
            return InspectTool._variable_detail(sym, file=file)

        if isinstance(sym, FunctionInfo):
            detail = InspectTool._function_detail(sym, file=file)
        else:
            detail = InspectTool._class_detail(sym, file=file)

        # Source code — only when requested
        if source and abs_path:
            detail["source"] = InspectTool._read_source(
                abs_path, sym.line_start, sym.line_end
            )

        return detail

    @staticmethod
    def _read_source(abs_file_path: str, start: int, end: int) -> str:
        """Read source lines from a file (absolute path)."""
        try:
            lines = Path(abs_file_path).read_text().splitlines()
            # 1-indexed → 0-indexed slice
            return "\n".join(lines[start - 1 : end])
        except (OSError, IndexError):
            return ""
