"""Execution flow tracing via entry point detection and BFS call graph.

Detects framework-specific entry points (cyclopts, click, Flask, FastAPI,
pytest, ``__main__`` guards) and traces execution flows through the
call graph using BFS.

Example::

    >>> from axm_ast.core.analyzer import analyze_package
    >>> from axm_ast.core.flows import find_entry_points, trace_flow
    >>> pkg = analyze_package(Path("src/mylib"))
    >>> entries = find_entry_points(pkg)
    >>> for e in entries:
    ...     print(f"{e.framework}: {e.name} ({e.module}:{e.line})")
"""

from __future__ import annotations

from collections import deque
from itertools import chain as iterchain
from typing import NamedTuple

from pydantic import BaseModel

from axm_ast.core.analyzer import _module_dotted_name
from axm_ast.core.callers import (
    _extract_call_site,
    _is_call_node,
    _node_text_safe,
    _update_context,
)
from axm_ast.core.parser import parse_source
from axm_ast.models.calls import CallSite
from axm_ast.models.nodes import ModuleInfo, PackageInfo

__all__ = [
    "EntryPoint",
    "FlowStep",
    "find_callees",
    "find_entry_points",
    "format_flows",
    "trace_flow",
]


# ─── Models ──────────────────────────────────────────────────────────────────


class EntryPoint(BaseModel):
    """A detected entry point in the codebase."""

    name: str
    module: str
    kind: str  # "decorator", "test", "main_guard", "export"
    line: int
    framework: str  # "cyclopts", "click", "flask", "fastapi", "pytest", "main", "all"


class FlowStep(BaseModel):
    """A single step in a traced execution flow."""

    name: str
    module: str
    line: int
    depth: int
    chain: list[str]


# ─── Decorator patterns ─────────────────────────────────────────────────────

# Maps framework → set of decorator prefixes that mark entry points.
_ENTRY_DECORATOR_PREFIXES: dict[str, list[str]] = {
    "cyclopts": ["app.default", "app.command"],
    "click": ["click.command", "click.group", "app.command"],
    "flask": ["app.route", "blueprint.route"],
    "fastapi": [
        "app.get",
        "app.post",
        "app.put",
        "app.delete",
        "app.patch",
        "router.get",
        "router.post",
        "router.put",
        "router.delete",
        "router.patch",
    ],
}


# ─── Entry point detection ───────────────────────────────────────────────────


class _FunctionRange(NamedTuple):
    """Start/end byte and name of a function definition."""

    name: str
    start_byte: int
    end_byte: int
    line: int


def find_entry_points(pkg: PackageInfo) -> list[EntryPoint]:
    """Detect framework-registered entry points across a package.

    Scans for:

    - **Decorator-based**: cyclopts, click, Flask, FastAPI
    - **Test functions**: ``test_*`` prefix
    - **Main guards**: ``if __name__ == "__main__"`` blocks
    - **``__all__`` exports**

    Args:
        pkg: Analyzed package info.

    Returns:
        List of EntryPoint objects sorted by module then line.
    """
    entries: list[EntryPoint] = []

    for mod in pkg.modules:
        mod_name = _module_dotted_name(mod.path, pkg.root)
        entries.extend(_scan_module_entries(mod, mod_name))

    entries.sort(key=lambda e: (e.module, e.line))
    return entries


def _scan_module_entries(mod: ModuleInfo, mod_name: str) -> list[EntryPoint]:
    """Scan a single module for entry points."""
    entries: list[EntryPoint] = []

    # Decorator-based + test function detection via AST
    source = mod.path.read_text(encoding="utf-8")
    tree = parse_source(source)
    _visit_entry_points(tree.root_node, source, mod_name, entries)

    # __all__ exports
    if mod.all_exports:
        for export_name in mod.all_exports:
            # Find the line of the exported symbol
            line = _find_symbol_line(mod, export_name)
            entries.append(
                EntryPoint(
                    name=export_name,
                    module=mod_name,
                    kind="export",
                    line=line,
                    framework="all",
                )
            )

    return entries


def _visit_entry_points(
    node: object,
    source: str,
    mod_name: str,
    entries: list[EntryPoint],
) -> None:
    """Walk the AST root and detect entry point patterns."""
    node_type = getattr(node, "type", "")

    if node_type == "function_definition":
        _check_function_entry(node, source, mod_name, entries)
    elif node_type == "if_statement":
        _check_main_guard(node, source, mod_name, entries)

    for child in getattr(node, "children", []):
        _visit_entry_points(child, source, mod_name, entries)


def _check_function_entry(
    node: object,
    source: str,
    mod_name: str,
    entries: list[EntryPoint],
) -> None:
    """Check if a function definition is an entry point."""
    # Get function name
    name_node = None
    for child in getattr(node, "children", []):
        if getattr(child, "type", "") == "identifier":
            name_node = child
            break

    if name_node is None:
        return

    func_name = _node_text_safe(name_node)
    start_point = getattr(node, "start_point", (0, 0))
    line = start_point[0] + 1

    # Check test function prefix
    if func_name.startswith("test_"):
        entries.append(
            EntryPoint(
                name=func_name,
                module=mod_name,
                kind="test",
                line=line,
                framework="pytest",
            )
        )
        return

    # Check decorators
    _check_decorators(node, func_name, line, mod_name, entries)


def _check_decorators(
    node: object,
    func_name: str,
    line: int,
    mod_name: str,
    entries: list[EntryPoint],
) -> None:
    """Check if the function has entry-point decorators."""
    # Look for decorated_definition parent — tree-sitter wraps decorated
    # functions in a `decorated_definition` node with `decorator` children.
    # But we're called on function_definition, so we need to check the parent.
    parent = getattr(node, "parent", None)
    parent_type = getattr(parent, "type", "")

    decorators: list[object] = []
    if parent_type == "decorated_definition":
        for child in getattr(parent, "children", []):
            if getattr(child, "type", "") == "decorator":
                decorators.append(child)

    for dec in decorators:
        dec_text = _node_text_safe(dec).lstrip("@").strip()
        framework = _match_decorator(dec_text)
        if framework is not None:
            dec_start = getattr(dec, "start_point", (0, 0))
            entries.append(
                EntryPoint(
                    name=func_name,
                    module=mod_name,
                    kind="decorator",
                    line=dec_start[0] + 1,
                    framework=framework,
                )
            )
            return  # One entry per function is enough


def _match_decorator(dec_text: str) -> str | None:
    """Match decorator text against known entry point patterns.

    Args:
        dec_text: Decorator text without leading ``@``.

    Returns:
        Framework name if matched, None otherwise.
    """
    for framework, prefixes in _ENTRY_DECORATOR_PREFIXES.items():
        for prefix in prefixes:
            if dec_text.startswith(prefix):
                return framework
    return None


def _check_main_guard(
    node: object,
    source: str,
    mod_name: str,
    entries: list[EntryPoint],
) -> None:
    """Check if an if-statement is a ``__main__`` guard."""
    text = _node_text_safe(node)
    if "__name__" in text and "__main__" in text:
        start_point = getattr(node, "start_point", (0, 0))
        entries.append(
            EntryPoint(
                name="__main__",
                module=mod_name,
                kind="main_guard",
                line=start_point[0] + 1,
                framework="main",
            )
        )


def _find_symbol_line(mod: ModuleInfo, name: str) -> int:
    """Find the line number of a symbol in a module."""
    for fn in mod.functions:
        if fn.name == name:
            return fn.line_start
    for cls in mod.classes:
        if cls.name == name:
            return cls.line_start
    return 1  # Fallback if not found


# ─── Callee resolution ──────────────────────────────────────────────────────


def find_callees(pkg: PackageInfo, symbol: str) -> list[CallSite]:
    """Find all functions called by a given symbol (forward call graph).

    This is the inverse of ``find_callers``: instead of asking "who calls X?",
    it asks "what does X call?".

    Args:
        pkg: Analyzed package info.
        symbol: Name of the function/method to inspect.

    Returns:
        List of CallSite objects for each call made by the symbol.

    Example:
        >>> callees = find_callees(pkg, "main")
        >>> for c in callees:
        ...     print(f"  calls {c.symbol} at {c.module}:{c.line}")
    """
    all_callees: list[CallSite] = []

    for mod in pkg.modules:
        mod_name = _module_dotted_name(mod.path, pkg.root)
        source = mod.path.read_text(encoding="utf-8")
        tree = parse_source(source)

        # Find the function definition node for this symbol
        func_ranges = _find_function_nodes(tree.root_node, symbol)
        for func_range in func_ranges:
            # Scope call extraction to this function's subtree
            calls = _extract_scoped_calls(tree.root_node, mod_name, source, func_range)
            all_callees.extend(calls)

    return all_callees


def _find_function_nodes(root: object, symbol: str) -> list[_FunctionRange]:
    """Find all function definition byte ranges matching the symbol name."""
    results: list[_FunctionRange] = []
    _walk_for_functions(root, symbol, results)
    return results


def _walk_for_functions(
    node: object, symbol: str, results: list[_FunctionRange]
) -> None:
    """Recursively walk AST to find function definitions with given name."""
    node_type = getattr(node, "type", "")

    if node_type == "function_definition":
        for child in getattr(node, "children", []):
            if getattr(child, "type", "") == "identifier":
                name = _node_text_safe(child)
                if name == symbol:
                    start_byte = getattr(node, "start_byte", 0)
                    end_byte = getattr(node, "end_byte", 0)
                    start_point = getattr(node, "start_point", (0, 0))
                    results.append(
                        _FunctionRange(
                            name=name,
                            start_byte=start_byte,
                            end_byte=end_byte,
                            line=start_point[0] + 1,
                        )
                    )
                break

    for child in getattr(node, "children", []):
        _walk_for_functions(child, symbol, results)


def _extract_scoped_calls(
    root: object,
    module_name: str,
    source: str,
    func_range: _FunctionRange,
) -> list[CallSite]:
    """Extract calls within a function's byte range."""
    calls: list[CallSite] = []
    _visit_scoped_calls(root, module_name, source, func_range, calls)
    return calls


def _visit_scoped_calls(
    node: object,
    module_name: str,
    source: str,
    func_range: _FunctionRange,
    calls: list[CallSite],
) -> None:
    """Visit calls within a byte range, skipping nodes outside scope."""
    node_start = getattr(node, "start_byte", 0)
    node_end = getattr(node, "end_byte", 0)

    # Skip nodes entirely outside the function range
    if node_end < func_range.start_byte or node_start > func_range.end_byte:
        return

    context = _update_context(node, None)

    if _is_call_node(node):
        call_site = _extract_call_site(node, module_name, source, context)
        if call_site is not None:
            # Don't include self-calls (the function calling itself recursively)
            if call_site.symbol != func_range.name:
                calls.append(call_site)

    for child in getattr(node, "children", []):
        _visit_scoped_calls(child, module_name, source, func_range, calls)


# ─── Flow tracing (BFS) ─────────────────────────────────────────────────────


def trace_flow(
    pkg: PackageInfo,
    entry: str,
    *,
    max_depth: int = 5,
) -> list[FlowStep]:
    """Trace execution flow from an entry point via BFS.

    Follows the forward call graph from *entry* up to *max_depth*
    levels deep. Uses a visited set to handle circular calls.

    Args:
        pkg: Analyzed package info.
        entry: Name of the entry point function to trace from.
        max_depth: Maximum BFS depth (default 5).

    Returns:
        List of FlowStep objects ordered by depth then discovery.

    Example:
        >>> steps = trace_flow(pkg, "main", max_depth=3)
        >>> for s in steps:
        ...     print(f"{'  ' * s.depth}{s.name} ({s.module}:{s.line})")
    """
    # Find the entry point location
    entry_mod, entry_line = _find_symbol_location(pkg, entry)
    if entry_mod is None:
        return []

    steps: list[FlowStep] = []
    visited: set[str] = {entry}
    queue: deque[tuple[str, int, list[str]]] = deque()
    queue.append((entry, 0, [entry]))

    # Add the entry point itself
    steps.append(
        FlowStep(
            name=entry,
            module=entry_mod,
            line=entry_line,
            depth=0,
            chain=[entry],
        )
    )

    while queue:
        current, depth, current_chain = queue.popleft()

        if depth >= max_depth:
            continue

        callees = find_callees(pkg, current)
        for callee in callees:
            if callee.symbol not in visited:
                visited.add(callee.symbol)
                new_chain = [*current_chain, callee.symbol]
                steps.append(
                    FlowStep(
                        name=callee.symbol,
                        module=callee.module,
                        line=callee.line,
                        depth=depth + 1,
                        chain=new_chain,
                    )
                )
                queue.append((callee.symbol, depth + 1, new_chain))

    return steps


def _find_symbol_location(pkg: PackageInfo, symbol: str) -> tuple[str | None, int]:
    """Find the module and line of a symbol in the package."""
    for mod in pkg.modules:
        for fn in iterchain(mod.functions, *(c.methods for c in mod.classes)):
            if fn.name == symbol:
                mod_name = _module_dotted_name(mod.path, pkg.root)
                return mod_name, fn.line_start
        for cls in mod.classes:
            if cls.name == symbol:
                mod_name = _module_dotted_name(mod.path, pkg.root)
                return mod_name, cls.line_start
    return None, 0


# ─── Formatting ──────────────────────────────────────────────────────────────


def format_flows(entry_points: list[EntryPoint]) -> str:
    """Format entry point results as human-readable grouped output.

    Args:
        entry_points: List of detected entry points.

    Returns:
        Formatted string grouped by framework.
    """
    if not entry_points:
        return "✅ No entry points detected."

    # Group by framework
    by_framework: dict[str, list[EntryPoint]] = {}
    for ep in entry_points:
        by_framework.setdefault(ep.framework, []).append(ep)

    lines: list[str] = [f"🔍 {len(entry_points)} entry point(s) detected:\n"]

    for framework, eps in sorted(by_framework.items()):
        lines.append(f"  📦 {framework} ({len(eps)}):")
        for ep in eps:
            lines.append(f"    • {ep.name} ({ep.module}:{ep.line}) [{ep.kind}]")
        lines.append("")

    return "\n".join(lines)
