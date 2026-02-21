"""InspectTool — inspect a single symbol by name."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

__all__ = ["InspectTool"]


class InspectTool(AXMTool):
    """Inspect a symbol across the package without knowing its file.

    Registered as ``ast_inspect`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "ast_inspect"

    def execute(
        self, *, path: str = ".", symbol: str | None = None, **kwargs: Any
    ) -> ToolResult:
        """Inspect a symbol by name.

        Args:
            path: Path to package directory.
            symbol: Symbol name to inspect (required).
                Supports dotted paths like ``ClassName.method``.

        Returns:
            ToolResult with symbol details.
        """
        if not symbol:
            return ToolResult(success=False, error="symbol parameter is required")

        try:
            project_path = Path(path).resolve()
            if not project_path.is_dir():
                return ToolResult(
                    success=False, error=f"Not a directory: {project_path}"
                )

            from axm_ast.core.analyzer import analyze_package, search_symbols

            pkg = analyze_package(project_path)

            # --- Dotted path resolution ---
            if "." in symbol:
                # Strategy: try module.function first, then ClassName.method
                result = self._resolve_module_symbol(pkg, symbol)
                if result is not None:
                    return result

                result = self._resolve_class_method(pkg, symbol)
                if result is not None:
                    return result

                return ToolResult(
                    success=False,
                    error=(
                        f"Symbol '{symbol}' not found"
                        " (tried module.symbol and Class.method)"
                    ),
                )

            # --- Simple name: function or class ---
            results = search_symbols(
                pkg,
                name=symbol,
                returns=None,
                kind=None,
                inherits=None,
            )

            if not results:
                return ToolResult(
                    success=False,
                    error=f"Symbol '{symbol}' not found",
                )

            sym = results[0]
            return ToolResult(
                success=True,
                data={"symbol": self._build_detail(sym)},
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

    def _resolve_module_symbol(self, pkg: Any, dotted: str) -> ToolResult | None:
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
            # Found a module — search for the symbol within it
            for fn in mod.functions:
                if fn.name == sym_name:
                    return ToolResult(
                        success=True,
                        data={"symbol": self._build_detail(fn)},
                    )
            for cls in mod.classes:
                if cls.name == sym_name:
                    return ToolResult(
                        success=True,
                        data={"symbol": self._build_detail(cls)},
                    )
            # Module found but symbol not in it
            return ToolResult(
                success=False,
                error=(f"Symbol '{sym_name}' not found in module '{mod_prefix}'"),
            )
        return None

    def _resolve_class_method(self, pkg: Any, dotted: str) -> ToolResult | None:
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
            (c for c in classes if hasattr(c, "methods") and c.name == class_name),
            None,
        )
        if cls is None:
            return None

        method = next((m for m in cls.methods if m.name == method_name), None)
        if method is None:
            return ToolResult(
                success=False,
                error=(f"Method '{method_name}' not found" f" in class '{class_name}'"),
            )

        return ToolResult(
            success=True,
            data={"symbol": self._build_detail(method)},
        )

    @staticmethod
    def _build_detail(sym: Any) -> dict[str, Any]:
        """Build detail dict from a FunctionInfo or ClassInfo."""
        detail: dict[str, Any] = {"name": sym.name}

        # Function-like
        if hasattr(sym, "signature"):
            detail["signature"] = sym.signature
        if hasattr(sym, "return_type"):
            detail["return_type"] = sym.return_type
        if hasattr(sym, "docstring"):
            detail["docstring"] = sym.docstring
        if hasattr(sym, "parameters"):
            detail["parameters"] = [
                {"name": p.name, "annotation": p.annotation, "default": p.default}
                for p in sym.parameters
            ]
        if hasattr(sym, "line"):
            detail["line"] = sym.line

        # Class-like
        if hasattr(sym, "bases"):
            detail["bases"] = sym.bases
        if hasattr(sym, "methods"):
            detail["methods"] = [m.name for m in sym.methods]

        # Module info
        detail["module"] = getattr(sym, "module", "")

        return detail
