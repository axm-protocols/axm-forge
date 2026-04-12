"""Detail-building helpers for InspectTool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm_ast.models.nodes import (
    ClassInfo,
    FunctionInfo,
    ModuleInfo,
    PackageInfo,
    VariableInfo,
)
from axm_ast.tools.inspect_text import (
    render_batch_text,
    render_class_text,
    render_function_text,
    render_module_text,
    render_symbol_text,
    render_variable_text,
)

__all__ = [
    "build_detail",
    "build_module_detail",
    "class_detail",
    "function_detail",
    "read_source",
    "relative_path",
    "render_batch_text",
    "render_class_text",
    "render_function_text",
    "render_module_text",
    "render_symbol_text",
    "render_variable_text",
    "variable_detail",
]


def relative_path(pkg: PackageInfo, mod_path: Path) -> str:
    """Compute relative path from package root."""
    try:
        return str(mod_path.relative_to(pkg.root.parent))
    except (ValueError, AttributeError):
        return str(mod_path)


def variable_detail(
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
    }
    if sym.annotation is not None:
        detail["annotation"] = sym.annotation
    if sym.value_repr is not None:
        detail["value_repr"] = sym.value_repr
    return detail


def function_detail(
    sym: FunctionInfo,
    *,
    file: str = "",
) -> dict[str, Any]:
    """Build detail dict from a FunctionInfo."""
    detail: dict[str, Any] = {
        "name": sym.name,
        "kind": "function",
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
    return detail


def class_detail(
    sym: ClassInfo,
    *,
    file: str = "",
) -> dict[str, Any]:
    """Build detail dict from a ClassInfo."""
    detail: dict[str, Any] = {
        "name": sym.name,
        "kind": "class",
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
    return detail


def read_source(abs_file_path: str, start: int, end: int) -> str:
    """Read source lines from a file (absolute path)."""
    try:
        lines = Path(abs_file_path).read_text().splitlines()
        return "\n".join(lines[start - 1 : end])
    except (OSError, IndexError):
        return ""


def build_detail(
    sym: FunctionInfo | ClassInfo | VariableInfo,
    *,
    file: str = "",
    abs_path: str = "",
    source: bool = False,
) -> dict[str, Any]:
    """Build detail dict from a FunctionInfo, ClassInfo, or VariableInfo."""
    if isinstance(sym, VariableInfo):
        detail = variable_detail(sym, file=file)
        if source and abs_path:
            detail["source"] = read_source(abs_path, sym.line, sym.line)
        return detail

    if isinstance(sym, FunctionInfo):
        detail = function_detail(sym, file=file)
    else:
        detail = class_detail(sym, file=file)

    if source and abs_path:
        detail["source"] = read_source(abs_path, sym.line_start, sym.line_end)

    return detail


def build_module_detail(pkg: PackageInfo, mod: ModuleInfo, name: str) -> dict[str, Any]:
    """Build detail dict for a module."""
    return {
        "name": name,
        "kind": "module",
        "file": relative_path(pkg, mod.path),
        "docstring": mod.docstring or "",
        "functions": [f.name for f in mod.functions],
        "classes": [c.name for c in mod.classes],
        "symbol_count": len(mod.functions) + len(mod.classes),
    }
