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

import sys
from collections import deque
from itertools import chain as iterchain
from pathlib import Path
from typing import NamedTuple

from pydantic import BaseModel, Field

from axm_ast.core.analyzer import module_dotted_name
from axm_ast.core.callers import (
    _extract_call_site,
    _is_call_node,
    _node_text_safe,
    _update_context,
)
from axm_ast.core.parser import parse_source
from axm_ast.models.calls import CallSite
from axm_ast.models.nodes import ImportInfo, ModuleInfo, PackageInfo

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
    resolved_module: str | None = Field(
        default=None,
        description="Dotted module path when resolved across modules",
    )
    source: str | None = Field(
        default=None,
        description="Source code of the symbol (when detail='source')",
    )


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
        mod_name = module_dotted_name(mod.path, pkg.root)
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
        mod_name = module_dotted_name(mod.path, pkg.root)
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


# Stdlib module names (Python 3.10+)
_STDLIB_MODULES: frozenset[str] = frozenset(getattr(sys, "stdlib_module_names", set()))

# Common builtins that appear as call targets but have no module.
_BUILTIN_NAMES: frozenset[str] = frozenset(
    {
        "len",
        "print",
        "isinstance",
        "issubclass",
        "type",
        "int",
        "str",
        "float",
        "bool",
        "list",
        "dict",
        "set",
        "tuple",
        "range",
        "enumerate",
        "zip",
        "map",
        "filter",
        "sorted",
        "reversed",
        "any",
        "all",
        "min",
        "max",
        "sum",
        "abs",
        "round",
        "repr",
        "hash",
        "id",
        "super",
        "object",
        "next",
        "iter",
        "getattr",
        "setattr",
        "hasattr",
        "delattr",
        "callable",
        "open",
        "vars",
        "dir",
    }
)


def _is_stdlib_or_builtin(name: str) -> bool:
    """Check if a name refers to a stdlib module or a builtin."""
    if name in _BUILTIN_NAMES:
        return True
    top = name.split(".")[0]
    return top in _STDLIB_MODULES


def _find_module_for_symbol(pkg: PackageInfo, symbol: str) -> ModuleInfo | None:
    """Find the ModuleInfo containing *symbol* in *pkg*."""
    for mod in pkg.modules:
        for fn in iterchain(mod.functions, *(c.methods for c in mod.classes)):
            if fn.name == symbol:
                return mod
        for cls in mod.classes:
            if cls.name == symbol:
                return mod
    return None


def _resolve_import(
    mod: ModuleInfo, symbol: str, pkg: PackageInfo
) -> tuple[Path | None, str]:
    """Resolve an imported *symbol* to the file containing its definition.

    Handles ``from X import Y`` and ``import X`` patterns, including
    relative imports.

    Returns:
        ``(file_path, dotted_module)`` or ``(None, "")`` if unresolvable.
    """
    for imp in mod.imports:
        if symbol in imp.names:
            # from X import Y
            return _resolve_import_info(imp, symbol, mod, pkg)
        if imp.alias == symbol and imp.module:
            # import X as alias
            return _module_to_path(imp.module, pkg.root)
    return None, ""


def _resolve_import_info(
    imp: ImportInfo, symbol: str, mod: ModuleInfo, pkg: PackageInfo
) -> tuple[Path | None, str]:
    """Resolve a single ImportInfo to a file path."""
    if imp.is_relative:
        return _resolve_relative_import(imp, mod, pkg)

    if imp.module is None:
        return None, ""

    # Try direct module: from foo.bar import Baz → foo/bar.py
    path, dotted = _module_to_path(imp.module, pkg.root)
    if path is not None:
        return path, dotted

    # Try sub-module: from foo import bar → foo/bar.py
    sub_mod = f"{imp.module}.{symbol}"
    path, dotted = _module_to_path(sub_mod, pkg.root)
    if path is not None:
        return path, dotted

    return None, ""


def _resolve_relative_import(
    imp: ImportInfo, mod: ModuleInfo, pkg: PackageInfo
) -> tuple[Path | None, str]:
    """Resolve a relative import like ``from .utils import helper``."""
    base = mod.path.parent
    # Go up `level - 1` directories (level=1 means current package)
    for _ in range(imp.level - 1):
        base = base.parent

    if imp.module:
        parts = imp.module.split(".")
        target = base / Path(*parts)
    else:
        target = base

    # Try as a .py file
    py_file = target.with_suffix(".py")
    if py_file.is_file():
        dotted = _path_to_dotted(py_file, pkg.root)
        return py_file, dotted

    # Try as a package (__init__.py)
    init_file = target / "__init__.py"
    if init_file.is_file():
        dotted = _path_to_dotted(init_file, pkg.root)
        return init_file, dotted

    return None, ""


_PROJECT_MARKERS: tuple[str, ...] = (".git", "pyproject.toml", "setup.py", "setup.cfg")


def _find_project_root(start: Path) -> Path:
    """Walk up from *start* to find the project root.

    Looks for common project markers (``.git``, ``pyproject.toml``,
    ``setup.py``, ``setup.cfg``).  Returns *start* if no marker is found.
    """
    current = start
    while current != current.parent:
        if any((current / m).exists() for m in _PROJECT_MARKERS):
            return current
        current = current.parent
    return start


def _module_to_path(dotted: str, root: Path) -> tuple[Path | None, str]:
    """Convert a dotted module name to a file path relative to *root*.

    Searches parent directories of *root* to find the module.
    Falls back to searching from the project root (detected via
    ``.git`` / ``pyproject.toml``) for sibling-package imports.
    """
    parts = dotted.split(".")

    # Search from root's parent (the containing directory)
    for search_base in [root.parent, root]:
        target = search_base / Path(*parts)

        # Try as .py file
        py_file = target.with_suffix(".py")
        if py_file.is_file():
            return py_file, dotted

        # Try as package
        init_file = target / "__init__.py"
        if init_file.is_file():
            return init_file, dotted

    # Fallback: walk up to project root for sibling-package imports
    # (e.g. tests/ importing from django/ in the same repo)
    project_root = _find_project_root(root)
    if project_root not in (root, root.parent):
        target = project_root / Path(*parts)
        py_file = target.with_suffix(".py")
        if py_file.is_file():
            return py_file, dotted
        init_file = target / "__init__.py"
        if init_file.is_file():
            return init_file, dotted

    return None, ""


def _path_to_dotted(path: Path, root: Path) -> str:
    """Convert a file path to a dotted module name."""
    try:
        rel = path.relative_to(root.parent)
    except ValueError:
        return path.stem
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else path.stem


def _parse_module_cached(path: Path, cache: dict[Path, PackageInfo]) -> PackageInfo:
    """Parse a single file into a minimal PackageInfo, with caching."""
    if path in cache:
        return cache[path]

    from axm_ast.core.analyzer import analyze_package

    # Determine the package root for the target module
    pkg_root = path.parent
    # Walk up to find the top-level package (directory without __init__.py
    # in its parent)
    while (pkg_root.parent / "__init__.py").is_file():
        pkg_root = pkg_root.parent

    mini_pkg = analyze_package(pkg_root)
    cache[path] = mini_pkg
    return mini_pkg


def trace_flow(
    pkg: PackageInfo,
    entry: str,
    *,
    max_depth: int = 5,
    cross_module: bool = False,
    detail: str = "trace",
) -> list[FlowStep]:
    """Trace execution flow from an entry point via BFS.

    Follows the forward call graph from *entry* up to *max_depth*
    levels deep. Uses a visited set to handle circular calls.

    Args:
        pkg: Analyzed package info.
        entry: Name of the entry point function to trace from.
        max_depth: Maximum BFS depth (default 5).
        cross_module: If True, resolve imports and continue BFS
            into external modules on-demand.
        detail: Level of detail — ``"trace"`` (default) returns
            names and positions only; ``"source"`` enriches each
            step with the function's source code.

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
    # Use (module, symbol) tuples to handle same-named symbols
    # in different modules.
    visited: set[tuple[str, str]] = {(entry_mod, entry)}
    # Queue: (symbol, depth, chain, source_pkg, source_module_dotted)
    queue: deque[tuple[str, int, list[str], PackageInfo, str]] = deque()
    queue.append((entry, 0, [entry], pkg, entry_mod))
    # BFS-scoped cache for on-demand module parsing
    parse_cache: dict[Path, PackageInfo] = {}

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
        current, depth, current_chain, current_pkg, current_mod = queue.popleft()

        if depth >= max_depth:
            continue

        callees = find_callees(current_pkg, current)
        for callee in callees:
            callee_key = (callee.module, callee.symbol)
            if callee_key not in visited:
                visited.add(callee_key)
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
                queue.append(
                    (callee.symbol, depth + 1, new_chain, current_pkg, callee.module)
                )

        if not cross_module:
            continue

        # Cross-module resolution: find symbols that were imported
        # but not defined locally.
        _resolve_cross_module_callees(
            callees,
            current_mod,
            current_pkg,
            pkg,
            depth,
            current_chain,
            visited,
            queue,
            steps,
            parse_cache,
        )

    if detail == "source":
        _enrich_steps_with_source(steps, pkg)

    return steps


def _enrich_steps_with_source(steps: list[FlowStep], pkg: PackageInfo) -> None:
    """Fill ``step.source`` for every step in *steps* in-place.

    Reads each module file and uses ``_find_function_nodes()`` to locate
    the exact byte range of the function.  Missing files and unresolvable
    modules yield ``source=None`` (no crash).
    """
    # Cache: module_path → source_bytes
    source_cache: dict[Path, bytes] = {}

    for step in steps:
        try:
            mod = _find_module_for_symbol(pkg, step.name)
            if mod is None:
                continue
            if mod.path not in source_cache:
                source_cache[mod.path] = mod.path.read_bytes()
            raw = source_cache[mod.path]
            tree = parse_source(raw.decode("utf-8", errors="replace"))
            ranges = _find_function_nodes(tree.root_node, step.name)
            if ranges:
                fr = ranges[0]
                # frozen model — use model_copy to set source
                step.source = raw[fr.start_byte : fr.end_byte].decode(
                    "utf-8", errors="replace"
                )
        except Exception:  # noqa: BLE001, S112
            continue  # graceful: leave source=None


def _resolve_cross_module_callees(  # noqa: PLR0913
    callees: list[CallSite],
    current_mod: str,
    current_pkg: PackageInfo,
    original_pkg: PackageInfo,
    depth: int,
    current_chain: list[str],
    visited: set[tuple[str, str]],
    queue: deque[tuple[str, int, list[str], PackageInfo, str]],
    steps: list[FlowStep],
    parse_cache: dict[Path, PackageInfo],
) -> None:
    """Try to resolve callees that are imported from other modules."""
    for callee in callees:
        symbol = callee.symbol
        if _is_stdlib_or_builtin(symbol):
            continue

        # Find the module where the current function lives
        source_mod = _find_module_for_symbol(current_pkg, callee.context or "")
        if source_mod is None:
            # Try to find by current_mod name
            for m in current_pkg.modules:
                mod_name = module_dotted_name(m.path, current_pkg.root)
                if mod_name == current_mod:
                    source_mod = m
                    break
        if source_mod is None:
            continue

        # Check if the callee is already defined in the package
        if _find_module_for_symbol(current_pkg, symbol) is not None:
            continue

        # Try to resolve the import
        resolved_path, resolved_dotted = _resolve_import(
            source_mod, symbol, original_pkg
        )
        if resolved_path is None or not resolved_path.is_file():
            continue

        # Parse the target module on-demand
        try:
            target_pkg = _parse_module_cached(resolved_path, parse_cache)
        except Exception:  # noqa: BLE001, S112
            continue

        # Find the symbol in the resolved package
        target_mod, target_line = _find_symbol_location(target_pkg, symbol)
        if target_mod is None:
            continue

        resolved_key = (resolved_dotted, symbol)
        if resolved_key in visited:
            continue
        visited.add(resolved_key)

        new_chain = [*current_chain, callee.symbol]
        steps.append(
            FlowStep(
                name=symbol,
                module=target_mod,
                line=target_line,
                depth=depth + 1,
                chain=new_chain,
                resolved_module=resolved_dotted,
            )
        )

        # Continue BFS into the resolved module
        queue.append((symbol, depth + 1, new_chain, target_pkg, target_mod))


def _find_symbol_location(pkg: PackageInfo, symbol: str) -> tuple[str | None, int]:
    """Find the module and line of a symbol in the package."""
    for mod in pkg.modules:
        for fn in iterchain(mod.functions, *(c.methods for c in mod.classes)):
            if fn.name == symbol:
                mod_name = module_dotted_name(mod.path, pkg.root)
                return mod_name, fn.line_start
        for cls in mod.classes:
            if cls.name == symbol:
                mod_name = module_dotted_name(mod.path, pkg.root)
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
