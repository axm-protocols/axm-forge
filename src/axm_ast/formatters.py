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
from axm_ast.docstring_parser import parse_docstring
from axm_ast.models.nodes import (
    ClassInfo,
    FunctionInfo,
    ModuleInfo,
    PackageInfo,
)

__all__ = [
    "filter_modules",
    "format_compressed",
    "format_json",
    "format_mermaid",
    "format_module_inspect_text",
    "format_symbol_text",
    "format_text",
    "format_toc",
]

DetailLevel = str  # "toc" | "summary" | "detailed" | "full"


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
        summary = parse_docstring(mod.docstring).summary
        if summary:
            lines.append(f"     {summary}")

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
        summary = parse_docstring(fn.docstring).summary
        if summary:
            lines.append(f"       {summary}")
    return lines


def _format_cls_text(cls: ClassInfo, *, detail: DetailLevel) -> list[str]:
    """Format a class as text lines."""
    bases = f"({', '.join(cls.bases)})" if cls.bases else ""
    icon = "🔒" if not cls.is_public else "🔓"
    lines = [f"     {icon} class {cls.name}{bases}"]
    if detail in ("detailed", "full") and cls.docstring:
        summary = parse_docstring(cls.docstring).summary
        if summary:
            lines.append(f"       {summary}")
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
        summary = parse_docstring(mod.docstring).summary
        if summary:
            lines.append(f'"""{summary}"""')

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
    summary = parse_docstring(fn.docstring).summary if fn.docstring else None
    if summary:
        lines.append(f'{pad}    """{summary}"""')
    else:
        lines[-1] += " ..."
    return lines


def _compress_class(cls: ClassInfo) -> list[str]:
    """Format a class in compressed mode."""
    bases = f"({', '.join(cls.bases)})" if cls.bases else ""
    lines = [f"class {cls.name}{bases}:"]
    if cls.docstring:
        summary = parse_docstring(cls.docstring).summary
        if summary:
            lines.append(f'    """{summary}"""')
    if cls.methods:
        for method in cls.methods:
            lines.extend(_compress_function(method, indent=1))
    elif not cls.docstring:
        lines.append("    ...")
    return lines


# ─── Single-symbol formatters (used by CLI inspect) ─────────────────────────


def _format_function_text(fn: FunctionInfo) -> list[str]:
    """Format a FunctionInfo for inspect output."""
    lines = [f"🔍 {fn.signature}"]
    parsed = parse_docstring(fn.docstring)
    if parsed.summary:
        lines.append(f"   {parsed.summary}")
    if parsed.raises:
        for exc, desc in parsed.raises:
            lines.append(f"   raises {exc}: {desc}")
    if parsed.examples:
        lines.append("   examples:")
        for ex in parsed.examples:
            for ex_line in ex.splitlines():
                lines.append(f"     {ex_line}")
    lines.append(f"   kind: {fn.kind.value}")
    lines.append(f"   lines: {fn.line_start}-{fn.line_end}")
    return lines


def _format_class_text(cls: ClassInfo) -> list[str]:
    """Format a ClassInfo for inspect output."""
    bases = f"({', '.join(cls.bases)})" if cls.bases else ""
    lines = [f"🔍 class {cls.name}{bases}"]
    parsed = parse_docstring(cls.docstring)
    if parsed.summary:
        lines.append(f"   {parsed.summary}")
    for m in cls.methods:
        lines.append(f"   · {m.signature}")
    return lines


def format_symbol_text(symbol: FunctionInfo | ClassInfo) -> str:
    """Format a single symbol for human-readable inspect output.

    Args:
        symbol: A function or class info object.

    Returns:
        Formatted text string.
    """
    if isinstance(symbol, FunctionInfo):
        lines = _format_function_text(symbol)
    else:
        lines = _format_class_text(symbol)
    return "\n".join(lines)


def _format_module_functions(mod: ModuleInfo) -> list[str]:
    """Format top-level functions of a module."""
    lines: list[str] = []
    for fn in mod.functions:
        pub = "🔓" if fn.is_public else "🔒"
        lines.append(f"  {pub} {fn.signature}")
        fn_summary = parse_docstring(fn.docstring).summary if fn.docstring else None
        if fn_summary:
            lines.append(f"     {fn_summary}")
    return lines


def _format_module_classes(mod: ModuleInfo) -> list[str]:
    """Format classes and their methods of a module."""
    lines: list[str] = []
    for cls in mod.classes:
        pub = "🔓" if cls.is_public else "🔒"
        bases = f"({', '.join(cls.bases)})" if cls.bases else ""
        lines.append(f"  {pub} class {cls.name}{bases}")
        for m in cls.methods:
            lines.append(f"     · {m.signature}")
    return lines


def format_module_inspect_text(mod: ModuleInfo) -> str:
    """Format a single module for human-readable inspect output.

    Args:
        mod: Module info object.

    Returns:
        Formatted text string.
    """
    lines: list[str] = [f"📄 {mod.path.name}"]
    summary = parse_docstring(mod.docstring).summary if mod.docstring else None
    if summary:
        lines.append(f"   {summary}")
    lines.append("")
    lines.extend(_format_module_functions(mod))
    lines.extend(_format_module_classes(mod))
    return "\n".join(lines)


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
        parsed = parse_docstring(fn.docstring)
        result["summary"] = parsed.summary
        if detail == "full":
            result["raises"] = [
                {"type": exc, "desc": desc} for exc, desc in parsed.raises
            ]
            result["examples"] = parsed.examples
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
        parsed = parse_docstring(cls.docstring)
        result["summary"] = parsed.summary
        result["methods"] = [
            _format_function_json(m, detail=detail) for m in cls.methods
        ]
        if detail == "full":
            result["raises"] = [
                {"type": exc, "desc": desc} for exc, desc in parsed.raises
            ]
            result["examples"] = parsed.examples
            result["decorators"] = cls.decorators
            result["line_start"] = cls.line_start
            result["line_end"] = cls.line_end
    return result


# ─── TOC formatter ───────────────────────────────────────────────────────────


def format_toc(pkg: PackageInfo) -> list[dict[str, Any]]:
    """Format package as a table-of-contents — module names and counts only.

    Returns lightweight module summaries WITHOUT individual function/class
    details.  Useful for agents to decide which modules to drill into.

    Args:
        pkg: Analyzed package info.

    Returns:
        List of module dicts with name, docstring, symbol_count,
        function_count, class_count.

    Example:
        >>> toc = format_toc(pkg)
        >>> toc[0]["name"]
        'core.analyzer'
    """
    from axm_ast.core.analyzer import _module_dotted_name

    modules: list[dict[str, Any]] = []
    for mod in pkg.modules:
        mod_name = _module_dotted_name(mod.path, pkg.root)
        summary = parse_docstring(mod.docstring).summary if mod.docstring else None
        func_count = len(mod.functions)
        cls_count = len(mod.classes)
        modules.append(
            {
                "name": mod_name,
                "docstring": summary,
                "function_count": func_count,
                "class_count": cls_count,
                "symbol_count": func_count + cls_count,
            }
        )
    return modules


# ─── Module filtering ────────────────────────────────────────────────────────


def filter_modules(pkg: PackageInfo, modules: list[str] | None) -> PackageInfo:
    """Return a shallow copy of *pkg* with modules filtered by name.

    Each term in *modules* is matched as a case-insensitive substring
    against the dotted module name.  If *modules* is ``None`` or empty,
    the original package is returned unchanged.

    Args:
        pkg: Analyzed package info.
        modules: Substring filters (OR logic).  ``None`` means no filter.

    Returns:
        PackageInfo with only matching modules (shallow copy).
    """
    if not modules:
        return pkg

    from axm_ast.core.analyzer import _module_dotted_name

    terms = [t.lower() for t in modules]
    filtered = [
        mod
        for mod in pkg.modules
        if any(t in _module_dotted_name(mod.path, pkg.root).lower() for t in terms)
    ]
    return PackageInfo(name=pkg.name, root=pkg.root, modules=filtered)


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
