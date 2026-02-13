"""Output formatters for axm-ast.

Provides four output formats (text, JSON, Mermaid, compressed) at three
detail levels (summary, detailed, full) with optional budget-based
truncation and PageRank-based symbol ranking.

Example:
    >>> from axm_ast.formatters import format_text
    >>> output = format_text(pkg, detail="summary")
    >>> print(output)
"""

from __future__ import annotations

from typing import Any

from axm_ast.core.analyzer import build_import_graph
from axm_ast.models.nodes import (
    ClassInfo,
    FunctionInfo,
    ModuleInfo,
    PackageInfo,
)

__all__ = [
    "format_compressed",
    "format_json",
    "format_mermaid",
    "format_text",
]

DetailLevel = str  # "summary" | "detailed" | "full"


# ─── Text formatter ──────────────────────────────────────────────────────────


def format_text(
    pkg: PackageInfo,
    *,
    detail: DetailLevel = "summary",
    budget: int | None = None,
    rank: bool = False,
) -> str:
    """Format package info as human-readable text.

    Args:
        pkg: Analyzed package info.
        detail: Level of detail — ``summary``, ``detailed``, or ``full``.
        budget: Maximum number of output lines. Truncates intelligently.
        rank: When True with a budget, sort symbols by importance
            (PageRank) so the most relevant appear first.

    Returns:
        Formatted text string.

    Example:
        >>> text = format_text(pkg, detail="summary")
        >>> print(text)
    """
    lines: list[str] = []
    lines.append(f"📦 {pkg.name}")
    lines.append(f"   root: {pkg.root}")
    lines.append(f"   modules: {len(pkg.modules)}")
    lines.append("")

    modules = _rank_modules(pkg) if rank else pkg.modules

    for mod in modules:
        lines.extend(_format_module_text(mod, pkg, detail=detail, rank=rank))
        lines.append("")

    if budget is not None and len(lines) > budget:
        lines = lines[:budget]
        lines.append("... (truncated)")

    return "\n".join(lines)


def _rank_modules(pkg: PackageInfo) -> list[ModuleInfo]:
    """Sort modules by their highest-ranked symbol."""
    from axm_ast.core.ranker import rank_symbols

    scores = rank_symbols(pkg)

    def _mod_score(mod: ModuleInfo) -> float:
        names = [f.name for f in mod.functions] + [c.name for c in mod.classes]
        return max((scores.get(n, 0.0) for n in names), default=0.0)

    return sorted(pkg.modules, key=_mod_score, reverse=True)


def _format_module_text(
    mod: ModuleInfo,
    pkg: PackageInfo,
    *,
    detail: DetailLevel,
    rank: bool = False,
) -> list[str]:
    """Format a single module as text lines."""
    from axm_ast.core.analyzer import _module_dotted_name

    lines: list[str] = []
    mod_name = _module_dotted_name(mod.path, pkg.root)
    lines.append(f"  📄 {mod_name}")

    if detail in ("detailed", "full") and mod.docstring:
        first_line = mod.docstring.strip().split("\n")[0]
        lines.append(f"     {first_line}")

    for fn in mod.functions:
        lines.extend(_format_fn_text(fn, detail=detail))

    for cls in mod.classes:
        lines.extend(_format_cls_text(cls, detail=detail))

    if detail == "full":
        lines.extend(_format_imports_text(mod))

    return lines


def _format_fn_text(fn: FunctionInfo, *, detail: DetailLevel) -> list[str]:
    """Format a function as text lines."""
    icon = "🔒" if not fn.is_public else "🔓"
    lines = [f"     {icon} {fn.signature}"]
    if detail in ("detailed", "full") and fn.docstring:
        first_line = fn.docstring.strip().split("\n")[0]
        lines.append(f"       {first_line}")
    return lines


def _format_cls_text(cls: ClassInfo, *, detail: DetailLevel) -> list[str]:
    """Format a class as text lines."""
    bases = f"({', '.join(cls.bases)})" if cls.bases else ""
    icon = "🔒" if not cls.is_public else "🔓"
    lines = [f"     {icon} class {cls.name}{bases}"]
    if detail in ("detailed", "full") and cls.docstring:
        first_line = cls.docstring.strip().split("\n")[0]
        lines.append(f"       {first_line}")
    if detail == "full":
        for method in cls.methods:
            lines.append(f"       · {method.signature}")
    return lines


def _format_imports_text(mod: ModuleInfo) -> list[str]:
    """Format module imports as text lines."""
    lines: list[str] = []
    for imp in mod.imports:
        module = imp.module or ""
        prefix = "." * imp.level if imp.is_relative else ""
        names_str = ", ".join(imp.names)
        lines.append(f"     import {prefix}{module} → {names_str}")
    return lines


# ─── Compressed formatter ────────────────────────────────────────────────────


def format_compressed(pkg: PackageInfo) -> str:
    """Format package as a compressed AI-friendly summary.

    Produces an intermediate format between ``stub`` and ``full``:
    keeps signatures, first docstring line, constants, ``__all__``,
    and relative imports — drops function bodies, full docstrings,
    absolute imports, and private symbols (unless in ``__all__``).

    Args:
        pkg: Analyzed package info.

    Returns:
        Compressed text string.

    Example:
        >>> print(format_compressed(pkg))
    """
    lines: list[str] = []
    for mod in pkg.modules:
        lines.extend(_compress_module(mod, pkg))
        lines.append("")
    return "\n".join(lines)


def _compress_module(mod: ModuleInfo, pkg: PackageInfo) -> list[str]:
    """Compress a single module."""
    from axm_ast.core.analyzer import _module_dotted_name

    lines: list[str] = []
    mod_name = _module_dotted_name(mod.path, pkg.root)
    lines.append(f"# {mod_name}")

    if mod.docstring:
        first_line = mod.docstring.strip().split("\n")[0]
        lines.append(f'"""{first_line}"""')

    lines.extend(_compress_variables(mod))
    lines.extend(_compress_relative_imports(mod))
    lines.append("")

    for fn in mod.functions:
        if _is_included(fn.name, mod):
            lines.extend(_compress_function(fn, indent=0))

    for cls in mod.classes:
        if _is_included(cls.name, mod):
            lines.extend(_compress_class(cls))

    return lines


def _is_included(name: str, mod: ModuleInfo) -> bool:
    """Check if a symbol should be included in compressed output."""
    if mod.all_exports is not None:
        return name in mod.all_exports
    return not name.startswith("_")


def _compress_variables(mod: ModuleInfo) -> list[str]:
    """Format module-level variables and constants."""
    lines: list[str] = []

    # Show __all__ from parsed exports
    if mod.all_exports is not None:
        exports = ", ".join(f'"{n}"' for n in mod.all_exports)
        lines.append(f"__all__ = [{exports}]")

    for var in mod.variables:
        if var.name.startswith("_"):
            continue
        ann = f": {var.annotation}" if var.annotation else ""
        val = f" = {var.value_repr}" if var.value_repr else ""
        lines.append(f"{var.name}{ann}{val}")
    return lines


def _compress_relative_imports(mod: ModuleInfo) -> list[str]:
    """Format only relative imports, filtering private names."""
    lines: list[str] = []
    for imp in mod.imports:
        if not imp.is_relative:
            continue
        # Filter out private imported names
        public_names = [n for n in imp.names if not n.startswith("_")]
        if not public_names:
            continue
        prefix = "." * imp.level
        module = imp.module or ""
        names = ", ".join(public_names)
        lines.append(f"from {prefix}{module} import {names}")
    return lines


def _compress_function(fn: FunctionInfo, indent: int = 0) -> list[str]:
    """Format a function in compressed mode."""
    pad = "    " * indent
    lines = [f"{pad}{fn.signature}:"]
    if fn.docstring:
        first_line = fn.docstring.strip().split("\n")[0]
        lines.append(f'{pad}    """{first_line}"""')
    else:
        lines[-1] += " ..."
    return lines


def _compress_class(cls: ClassInfo) -> list[str]:
    """Format a class in compressed mode."""
    bases = f"({', '.join(cls.bases)})" if cls.bases else ""
    lines = [f"class {cls.name}{bases}:"]
    if cls.docstring:
        first_line = cls.docstring.strip().split("\n")[0]
        lines.append(f'    """{first_line}"""')
    if cls.methods:
        for method in cls.methods:
            lines.extend(_compress_function(method, indent=1))
    elif not cls.docstring:
        lines.append("    ...")
    return lines


# ─── JSON formatter ──────────────────────────────────────────────────────────


def format_json(
    pkg: PackageInfo,
    *,
    detail: DetailLevel = "summary",
) -> dict[str, Any]:
    """Format package info as a JSON-serializable dict.

    Args:
        pkg: Analyzed package info.
        detail: Level of detail — ``summary``, ``detailed``, or ``full``.

    Returns:
        JSON-serializable dictionary.

    Example:
        >>> data = format_json(pkg, detail="summary")
        >>> data["name"]
        'sample_pkg'
    """
    result: dict[str, Any] = {
        "name": pkg.name,
        "root": str(pkg.root),
        "module_count": len(pkg.modules),
        "modules": [
            _format_module_json(mod, pkg, detail=detail) for mod in pkg.modules
        ],
    }

    if detail == "full":
        result["dependency_graph"] = build_import_graph(pkg)

    return result


def _format_module_json(
    mod: ModuleInfo,
    pkg: PackageInfo,
    *,
    detail: DetailLevel,
) -> dict[str, Any]:
    """Format a single module as a JSON dict."""
    from axm_ast.core.analyzer import _module_dotted_name

    result: dict[str, Any] = {
        "name": _module_dotted_name(mod.path, pkg.root),
        "path": str(mod.path),
    }

    # Functions
    result["functions"] = [
        _format_function_json(fn, detail=detail) for fn in mod.functions
    ]

    # Classes
    result["classes"] = [_format_class_json(cls, detail=detail) for cls in mod.classes]

    if detail in ("detailed", "full"):
        result["docstring"] = mod.docstring

    if detail == "full":
        result["imports"] = [
            {
                "module": imp.module,
                "names": imp.names,
                "is_relative": imp.is_relative,
            }
            for imp in mod.imports
        ]
        result["variables"] = [
            {"name": v.name, "annotation": v.annotation, "value": v.value_repr}
            for v in mod.variables
        ]

    return result


def _format_function_json(fn: FunctionInfo, *, detail: DetailLevel) -> dict[str, Any]:
    """Format a function as a JSON dict."""
    result: dict[str, Any] = {
        "name": fn.name,
        "signature": fn.signature,
        "kind": fn.kind.value,
        "is_public": fn.is_public,
    }
    if detail in ("detailed", "full"):
        result["docstring"] = fn.docstring
        result["params"] = [
            {
                "name": p.name,
                "annotation": p.annotation,
                "default": p.default,
            }
            for p in fn.params
        ]
        result["return_type"] = fn.return_type
        result["decorators"] = fn.decorators
    if detail == "full":
        result["line_start"] = fn.line_start
        result["line_end"] = fn.line_end
        result["is_async"] = fn.is_async
    return result


def _format_class_json(cls: ClassInfo, *, detail: DetailLevel) -> dict[str, Any]:
    """Format a class as a JSON dict."""
    result: dict[str, Any] = {
        "name": cls.name,
        "bases": cls.bases,
        "is_public": cls.is_public,
    }
    if detail in ("detailed", "full"):
        result["docstring"] = cls.docstring
        result["methods"] = [
            _format_function_json(m, detail=detail) for m in cls.methods
        ]
        result["decorators"] = cls.decorators
    if detail == "full":
        result["line_start"] = cls.line_start
        result["line_end"] = cls.line_end
    return result


# ─── Mermaid formatter ───────────────────────────────────────────────────────


def format_mermaid(pkg: PackageInfo) -> str:
    """Format the import graph as a Mermaid flowchart.

    Args:
        pkg: Analyzed package info.

    Returns:
        Mermaid diagram string.

    Example:
        >>> print(format_mermaid(pkg))
        graph TD
            cli --> core
    """
    graph = build_import_graph(pkg)
    lines = ["graph TD"]

    # Add all modules as nodes
    from axm_ast.core.analyzer import _module_dotted_name

    for mod in pkg.modules:
        name = _module_dotted_name(mod.path, pkg.root)
        safe_name = name.replace(".", "_")
        lines.append(f'    {safe_name}["{name}"]')

    # Add edges
    for src, targets in graph.items():
        safe_src = src.replace(".", "_")
        for target in targets:
            safe_target = target.replace(".", "_")
            lines.append(f"    {safe_src} --> {safe_target}")

    return "\n".join(lines)
