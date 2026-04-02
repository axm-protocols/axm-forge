"""Symbol resolution helpers for InspectTool."""

from __future__ import annotations

from pathlib import Path

from axm.tools.base import ToolResult

from axm_ast.core.analyzer import find_module_for_symbol, search_symbols
from axm_ast.models.nodes import (
    ClassInfo,
    FunctionInfo,
    ModuleInfo,
    PackageInfo,
    VariableInfo,
)

from .inspect_detail import build_detail, build_module_detail, relative_path

__all__ = [
    "find_module_for_symbol",
    "find_symbol_abs_path",
    "find_symbol_file",
    "inspect_dotted",
    "inspect_module",
    "resolve_class_method",
    "resolve_module",
    "resolve_module_symbol",
    "resolve_path",
    "search_symbols",
]


def resolve_path(path: str) -> Path | ToolResult:
    """Resolve and validate project path."""
    project_path = Path(path).resolve()
    if not project_path.is_dir():
        return ToolResult(success=False, error=f"Not a directory: {project_path}")
    return project_path


def find_symbol_file(
    pkg: PackageInfo, sym: FunctionInfo | ClassInfo | VariableInfo
) -> str:
    """Find the relative file path for a symbol within the package."""
    mod = find_module_for_symbol(pkg, sym)
    if mod is not None:
        return relative_path(pkg, mod.path)
    return ""


def find_symbol_abs_path(
    pkg: PackageInfo, sym: FunctionInfo | ClassInfo | VariableInfo
) -> str:
    """Find the absolute file path for a symbol within the package."""
    mod = find_module_for_symbol(pkg, sym)
    if mod is not None:
        return str(mod.path)
    return ""


def resolve_module(
    pkg: PackageInfo,
    name: str,
) -> ModuleInfo | ToolResult | None:
    """Resolve a name to a module via exact or substring match."""
    mod_names = pkg.module_names
    name_to_mod: dict[str, ModuleInfo] = dict(zip(mod_names, pkg.modules, strict=True))

    mod = name_to_mod.get(name)
    if mod is not None:
        return mod

    matches = [n for n in mod_names if name in n]
    if len(matches) == 1:
        return name_to_mod[matches[0]]
    if len(matches) > 1:
        return ToolResult(
            success=False,
            error=(f"Multiple modules match '{name}': {', '.join(sorted(matches))}"),
        )
    return None


def inspect_module(pkg: PackageInfo, name: str) -> ToolResult | None:
    """Try to resolve *name* as a module name and return module metadata."""
    mod = resolve_module(pkg, name)
    if mod is None or isinstance(mod, ToolResult):
        return mod

    detail = build_module_detail(pkg, mod, name)
    return ToolResult(success=True, data={"symbol": detail})


def resolve_module_symbol(
    pkg: PackageInfo, dotted: str, *, source: bool = False
) -> ToolResult | None:
    """Try to resolve ``dotted`` as ``module_name.symbol_name``.

    Tries longest module prefix first (e.g. ``core.checker`` before ``core``).
    Returns None if no module prefix matches.
    """
    mod_names = pkg.module_names
    name_to_mod = dict(zip(mod_names, pkg.modules, strict=True))

    parts = dotted.split(".")
    for split_at in range(len(parts) - 1, 0, -1):
        mod_prefix = ".".join(parts[:split_at])
        sym_name = ".".join(parts[split_at:])
        mod = name_to_mod.get(mod_prefix)
        if mod is None:
            continue
        file_rel = relative_path(pkg, mod.path)
        abs_mod = str(mod.path)
        for fn in mod.functions:
            if fn.name == sym_name:
                return ToolResult(
                    success=True,
                    data={
                        "symbol": build_detail(
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
                        "symbol": build_detail(
                            cls,
                            file=file_rel,
                            abs_path=abs_mod,
                            source=source,
                        )
                    },
                )
        return ToolResult(
            success=False,
            error=(f"Symbol '{sym_name}' not found in module '{mod_prefix}'"),
        )
    return None


def resolve_class_method(
    pkg: PackageInfo, dotted: str, *, source: bool = False
) -> ToolResult | None:
    """Try to resolve ``dotted`` as ``ClassName.method_name``.

    Returns None if no class matches.
    """
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

    file_path = find_symbol_file(pkg, cls)
    abs_path = find_symbol_abs_path(pkg, cls)
    return ToolResult(
        success=True,
        data={
            "symbol": build_detail(
                method,
                file=file_path,
                abs_path=abs_path,
                source=source,
            )
        },
    )


def inspect_dotted(
    pkg: PackageInfo, symbol: str, *, source: bool = False
) -> ToolResult:
    """Resolve a dotted symbol (module, module.symbol, or Class.method)."""
    result = inspect_module(pkg, symbol)
    if result is not None:
        return result

    result = resolve_module_symbol(pkg, symbol, source=source)
    if result is not None:
        return result

    result = resolve_class_method(pkg, symbol, source=source)
    if result is not None:
        return result

    return ToolResult(
        success=False,
        error=(
            f"Symbol '{symbol}' not found"
            " (tried module name, module.symbol, and Class.method)"
        ),
    )
