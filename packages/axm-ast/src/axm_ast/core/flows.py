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

import logging
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NamedTuple

from pydantic import BaseModel, ConfigDict, Field

from axm_ast.core.analyzer import find_module_for_symbol, module_dotted_name
from axm_ast.core.callers import (
    _extract_call_site,
    _is_call_node,
    _node_text_safe,
    _update_context,
)
from axm_ast.core.parser import parse_source
from axm_ast.models.calls import CallSite
from axm_ast.models.nodes import ImportInfo, ModuleInfo, PackageInfo

logger = logging.getLogger(__name__)

__all__ = [
    "EntryPoint",
    "FlowStep",
    "build_callee_index",
    "find_callees",
    "find_entry_points",
    "format_flow_compact",
    "format_flows",
    "trace_flow",
]


# ─── Models ──────────────────────────────────────────────────────────────────


class EntryPoint(BaseModel):
    """A detected entry point in the codebase."""

    model_config = ConfigDict(extra="forbid")

    name: str
    module: str
    kind: str  # "decorator", "test", "main_guard", "export"
    line: int
    framework: str  # "cyclopts", "click", "flask", "fastapi", "pytest", "main", "all"


class FlowStep(BaseModel):
    """A single step in a traced execution flow."""

    model_config = ConfigDict(extra="forbid")

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


def find_callees(
    pkg: PackageInfo,
    symbol: str,
    *,
    _parse_cache: dict[str, tuple[Any, str]] | None = None,
) -> list[CallSite]:
    """Find all functions called by a given symbol (forward call graph).

    This is the inverse of ``find_callers``: instead of asking "who calls X?",
    it asks "what does X call?".

    Args:
        pkg: Analyzed package info.
        symbol: Name of the function/method to inspect.
        _parse_cache: Optional cache of ``{path_str: (tree, source)}``
            to avoid re-parsing the same file.  Shared across BFS
            iterations in ``trace_flow``.

    Returns:
        List of CallSite objects for each call made by the symbol.

    Example:
        >>> callees = find_callees(pkg, "main")
        >>> for c in callees:
        ...     print(f"  calls {c.symbol} at {c.module}:{c.line}")
    """
    cache = _parse_cache if _parse_cache is not None else {}
    all_callees: list[CallSite] = []

    for mod in pkg.modules:
        mod_name = module_dotted_name(mod.path, pkg.root)
        path_key = str(mod.path)

        if path_key in cache:
            tree, source = cache[path_key]
        else:
            source = mod.path.read_text(encoding="utf-8")
            tree = parse_source(source)
            cache[path_key] = (tree, source)

        # Find the function definition node for this symbol
        func_ranges = _find_function_nodes(tree.root_node, symbol)
        for func_range in func_ranges:
            # Scope call extraction to this function's subtree
            calls = _extract_scoped_calls(tree.root_node, mod_name, source, func_range)
            all_callees.extend(calls)

    return all_callees


def build_callee_index(
    pkg: PackageInfo,
) -> dict[tuple[str, str], list[CallSite]]:
    """Pre-compute a callee index for the entire package in one pass.

    Instead of scanning all modules per symbol (O(modules x AST) per BFS step),
    this builds a ``{(module, symbol): [CallSite]}`` dict in a single pass.
    BFS then uses O(1) dict lookups.

    Args:
        pkg: Analyzed package info.

    Returns:
        Dict mapping ``(module_dotted_name, function_name)`` to callees.
    """
    index: dict[tuple[str, str], list[CallSite]] = {}

    for mod in pkg.modules:
        mod_name = module_dotted_name(mod.path, pkg.root)
        source = mod.path.read_text(encoding="utf-8")
        tree = parse_source(source)

        func_ranges = _find_all_function_ranges(tree.root_node)
        for fr in func_ranges:
            calls = _extract_scoped_calls(tree.root_node, mod_name, source, fr)
            index[(mod_name, fr.name)] = calls

    return index


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

    if node_type in ("function_definition", "class_definition"):
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


def _find_all_function_ranges(root: object) -> list[_FunctionRange]:
    """Find all function/class definition byte ranges in an AST."""
    results: list[_FunctionRange] = []
    _walk_all_functions(root, results)
    return results


def _walk_all_functions(node: object, results: list[_FunctionRange]) -> None:
    """Recursively walk AST to collect all function/class definitions."""
    node_type = getattr(node, "type", "")

    if node_type in ("function_definition", "class_definition"):
        for child in getattr(node, "children", []):
            if getattr(child, "type", "") == "identifier":
                name = _node_text_safe(child)
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
        _walk_all_functions(child, results)


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


def _build_package_symbols(pkg: PackageInfo) -> frozenset[str]:
    """Collect all symbol names defined in the package.

    Used by ``trace_flow`` to distinguish project-defined callees from
    external/stdlib method calls (e.g. ``logger.info`` → ``info`` is not
    in the package, so it's external).
    """
    names: set[str] = set()
    for mod in pkg.modules:
        for fn in mod.functions:
            names.add(fn.name)
        for cls in mod.classes:
            names.add(cls.name)
            for method in cls.methods:
                names.add(method.name)
    return frozenset(names)


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


@dataclass
class _CrossModuleContext:
    """BFS state shared across cross-module resolution iterations."""

    visited: set[tuple[str, str]]
    queue: deque[tuple[str, int, list[str], PackageInfo, str]]
    steps: list[FlowStep]
    parse_cache: dict[str, tuple[Any, str]] = field(default_factory=dict)
    detail: str = "trace"
    exclude_stdlib: bool = True
    pkg_symbols: frozenset[str] = field(default_factory=frozenset)


def _process_local_callees(  # noqa: PLR0913
    *,
    callees: list[CallSite],
    exclude_stdlib: bool,
    pkg_symbols: frozenset[str],
    visited: set[tuple[str, str]],
    current_chain: list[str],
    depth: int,
    steps: list[FlowStep],
    queue: deque[tuple[str, int, list[str], PackageInfo, str]],
    current_pkg: PackageInfo,
) -> None:
    """Filter stdlib/visited callees and enqueue new discoveries."""
    for callee in callees:
        if exclude_stdlib and (
            _is_stdlib_or_builtin(callee.symbol) or callee.symbol not in pkg_symbols
        ):
            continue
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


def trace_flow(  # noqa: PLR0913
    pkg: PackageInfo,
    entry: str,
    *,
    max_depth: int = 5,
    cross_module: bool = False,
    detail: str = "trace",
    callee_index: dict[tuple[str, str], list[CallSite]] | None = None,
    exclude_stdlib: bool = True,
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
        callee_index: Optional pre-computed index from
            :func:`build_callee_index`.  When provided, BFS uses
            O(1) dict lookups instead of scanning all modules.
        exclude_stdlib: If True (default), skip callees whose name
            matches a stdlib module or Python builtin (e.g. ``len``,
            ``isinstance``).  Set to False to include them.

    Returns:
        List of FlowStep objects ordered by depth then discovery.

    Example:
        >>> steps = trace_flow(pkg, "main", max_depth=3)
        >>> for s in steps:
        ...     print(f"{'  ' * s.depth}{s.name} ({s.module}:{s.line})")
    """
    t0 = time.perf_counter()

    # Find the entry point location
    entry_mod, entry_line = _find_symbol_location(pkg, entry)
    if entry_mod is None:
        return []

    # Pre-compute set of symbols defined in the package so we can
    # distinguish project callees from stdlib method calls (e.g.
    # logger.info → "info" is not in pkg_symbols → skip).
    pkg_symbols = _build_package_symbols(pkg) if exclude_stdlib else frozenset()

    steps: list[FlowStep] = []
    # Use (module, symbol) tuples to handle same-named symbols
    # in different modules.
    visited: set[tuple[str, str]] = {(entry_mod, entry)}
    # Queue: (symbol, depth, chain, source_pkg, source_module_dotted)
    queue: deque[tuple[str, int, list[str], PackageInfo, str]] = deque()
    queue.append((entry, 0, [entry], pkg, entry_mod))

    # Shared BFS context for cross-module resolution
    ctx = _CrossModuleContext(
        visited=visited,
        queue=queue,
        steps=steps,
        detail=detail,
        exclude_stdlib=exclude_stdlib,
        pkg_symbols=pkg_symbols,
    )

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

        if callee_index is not None:
            callees = callee_index.get((current_mod, current), [])
        else:
            callees = find_callees(current_pkg, current, _parse_cache=ctx.parse_cache)
        _process_local_callees(
            callees=callees,
            exclude_stdlib=exclude_stdlib,
            pkg_symbols=pkg_symbols,
            visited=visited,
            current_chain=current_chain,
            depth=depth,
            steps=steps,
            queue=queue,
            current_pkg=current_pkg,
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
            ctx,
        )

    if detail == "source":
        _enrich_steps_with_source(steps, pkg)

    elapsed = time.perf_counter() - t0
    logger.debug(
        "Traced %s in %.2fs (%d steps, depth=%d)",
        entry,
        elapsed,
        len(steps),
        max_depth,
    )

    return steps


@dataclass
class _SymbolLocation:
    """Lightweight symbol location from tree-sitter (no full pkg parse)."""

    line: int
    source: str | None = None


def _locate_symbol(
    path: Path, symbol: str, *, with_source: bool = False
) -> _SymbolLocation | None:
    """Find *symbol* in *path* via tree-sitter.  Returns line (+ source).

    This avoids the heavyweight ``analyze_package`` path — it only parses
    the single file, making cross-module resolution O(1) per symbol.
    """
    try:
        raw = path.read_bytes()
        tree = parse_source(raw.decode("utf-8", errors="replace"))
        ranges = _find_function_nodes(tree.root_node, symbol)
        if not ranges:
            return None
        fr = ranges[0]
        source = None
        if with_source:
            source = raw[fr.start_byte : fr.end_byte].decode("utf-8", errors="replace")
        return _SymbolLocation(line=fr.line, source=source)
    except Exception:  # noqa: BLE001
        logger.debug("Failed to locate symbol %r in %s", symbol, path, exc_info=True)
        return None


def _enrich_steps_with_source(steps: list[FlowStep], pkg: PackageInfo) -> None:
    """Fill ``step.source`` for every step in *steps* in-place.

    Uses ``_locate_symbol()`` to read each module file and extract the
    function source.  Steps that already have ``source`` set (e.g. from
    cross-module resolution) are skipped.
    """
    for step in steps:
        if step.source is not None:
            continue  # already enriched (cross-module resolution)
        mod = find_module_for_symbol(pkg, step.name)
        if mod is None:
            continue
        loc = _locate_symbol(mod.path, step.name, with_source=True)
        if loc is not None:
            step.source = loc.source


def _parse_import_from_node(node: object) -> tuple[str, list[str]]:
    """Extract module path and imported names from an import_from_statement.

    Uses position-based parsing: children before the ``import`` keyword
    are the module path, children after are the imported names.

    Args:
        node: A tree-sitter ``import_from_statement`` node.

    Returns:
        ``(module_path, [imported_name, ...])``.
    """
    seen_import_kw = False
    import_module = ""
    imported: list[str] = []

    for child in getattr(node, "children", []):
        ct = getattr(child, "type", "")
        text = _node_text_safe(child)
        if ct == "import":
            seen_import_kw = True
        elif not seen_import_kw and ct in ("dotted_name", "relative_import"):
            import_module = text
        elif seen_import_kw and ct in ("dotted_name", "identifier"):
            imported.append(text)

    return import_module, imported


def _resolve_relative_module(import_module: str, resolved_dotted: str) -> str:
    """Resolve a relative import module path to an absolute dotted name.

    Example::

        >>> _resolve_relative_module(".response", "django.http")
        'django.http.response'

    Args:
        import_module: The raw import path (e.g. ``".response"``).
        resolved_dotted: The dotted name of the current module.

    Returns:
        Absolute dotted module name.
    """
    base_parts = resolved_dotted.split(".")
    dots = len(import_module) - len(import_module.lstrip("."))
    rel_name = import_module.lstrip(".")
    base = ".".join(base_parts[: max(1, len(base_parts) - dots + 1)])
    return f"{base}.{rel_name}" if rel_name else base


def _follow_reexport(
    resolved_path: Path,
    resolved_dotted: str,
    symbol: str,
    original_pkg: PackageInfo,
    *,
    with_source: bool = False,
) -> tuple[_SymbolLocation | None, Path, str]:
    """Follow one level of re-export in *resolved_path*.

    Handles the common ``__init__.py`` pattern::

        from .response import HttpResponse   # re-export

    Returns ``(loc, actual_path, actual_dotted)`` or ``(None, -, -)``
    if the symbol cannot be found.
    """
    try:
        raw = resolved_path.read_bytes()
        tree = parse_source(raw.decode("utf-8", errors="replace"))
    except Exception:  # noqa: BLE001
        logger.debug(
            "Failed to parse %s for re-export resolution",
            resolved_path,
            exc_info=True,
        )
        return None, resolved_path, resolved_dotted

    for node in getattr(tree.root_node, "children", []):
        if getattr(node, "type", "") != "import_from_statement":
            continue

        import_module, imported = _parse_import_from_node(node)

        if symbol not in imported or not import_module:
            continue

        # Resolve relative imports
        if import_module.startswith("."):
            import_module = _resolve_relative_module(import_module, resolved_dotted)

        # Try to find the file for this module
        target_path, target_dotted = _module_to_path(import_module, original_pkg.root)
        if target_path is None or not target_path.is_file():
            continue

        loc = _locate_symbol(target_path, symbol, with_source=with_source)
        if loc is not None:
            return loc, target_path, target_dotted or import_module

    return None, resolved_path, resolved_dotted


def _find_source_module(
    pkg: PackageInfo,
    context: str,
    current_mod: str,
) -> ModuleInfo | None:
    """Find the module where the callee's context function lives.

    First tries :func:`find_module_for_symbol` by *context* name, then
    falls back to matching modules by dotted name against *current_mod*.
    """
    if context:
        result = find_module_for_symbol(pkg, context)
        if result is not None:
            return result
    for m in pkg.modules:
        if module_dotted_name(m.path, pkg.root) == current_mod:
            return m
    return None


def _try_resolve_callee(
    callee: CallSite,
    pkg: PackageInfo,
) -> bool | None:
    """Check whether *callee* should be resolved cross-module.

    Returns ``None`` when the callee should be skipped (stdlib/builtin
    or already defined locally in *pkg*).
    """
    if _is_stdlib_or_builtin(callee.symbol):
        return None
    if find_module_for_symbol(pkg, callee.symbol) is not None:
        return None
    return True


def _resolve_cross_module_callees(  # noqa: PLR0913
    callees: list[CallSite],
    current_mod: str,
    current_pkg: PackageInfo,
    original_pkg: PackageInfo,
    depth: int,
    current_chain: list[str],
    ctx: _CrossModuleContext,
) -> None:
    """Try to resolve callees that are imported from other modules."""
    for callee in callees:
        if _try_resolve_callee(callee, current_pkg) is None:
            continue

        source_mod = _find_source_module(current_pkg, callee.context or "", current_mod)
        if source_mod is None:
            continue

        symbol = callee.symbol
        # Try to resolve the import
        resolved_path, resolved_dotted = _resolve_import(
            source_mod, symbol, original_pkg
        )
        if resolved_path is None or not resolved_path.is_file():
            continue

        # Lightweight symbol lookup — tree-sitter on the single file,
        # no full package parse, no BFS continuation into external code.
        loc = _locate_symbol(
            resolved_path, symbol, with_source=(ctx.detail == "source")
        )
        if loc is None:
            # Symbol not defined here — follow re-exports (e.g.
            # __init__.py that does ``from .response import HttpResponse``)
            loc, resolved_path, resolved_dotted = _follow_reexport(
                resolved_path,
                resolved_dotted,
                symbol,
                original_pkg,
                with_source=(ctx.detail == "source"),
            )
        if loc is None:
            continue

        resolved_key = (resolved_dotted, symbol)
        if resolved_key in ctx.visited:
            continue
        ctx.visited.add(resolved_key)

        new_chain = [*current_chain, callee.symbol]
        ctx.steps.append(
            FlowStep(
                name=symbol,
                module=resolved_dotted,
                line=loc.line,
                depth=depth + 1,
                chain=new_chain,
                resolved_module=resolved_dotted,
                source=loc.source,
            )
        )


def _find_qualified_location(
    pkg: PackageInfo, class_name: str, method_name: str
) -> tuple[str | None, int]:
    """Find the module and line of a qualified ``ClassName.method`` symbol."""
    for mod in pkg.modules:
        for cls in mod.classes:
            if cls.name != class_name:
                continue
            for method in cls.methods:
                if method.name == method_name:
                    return module_dotted_name(mod.path, pkg.root), method.line_start
    return None, 0


def _find_short_location(pkg: PackageInfo, symbol: str) -> tuple[str | None, int]:
    """Find the module and line of a short (unqualified) symbol name."""
    for mod in pkg.modules:
        for fn in mod.functions:
            if fn.name == symbol:
                return module_dotted_name(mod.path, pkg.root), fn.line_start
        for cls in mod.classes:
            if cls.name == symbol:
                return module_dotted_name(mod.path, pkg.root), cls.line_start
            for method in cls.methods:
                if method.name == symbol:
                    return module_dotted_name(mod.path, pkg.root), method.line_start
    return None, 0


def _find_symbol_location(pkg: PackageInfo, symbol: str) -> tuple[str | None, int]:
    """Find the module and line of a symbol in the package.

    Supports both short names (``bar``) and qualified names
    (``Foo.bar``) where the prefix is a class name.
    """
    if "." in symbol:
        class_name, method_name = symbol.rsplit(".", 1)
        result = _find_qualified_location(pkg, class_name, method_name)
        if result[0] is not None:
            return result
        # Fall through to short-name search if qualified lookup fails
    return _find_short_location(pkg, symbol)


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


def format_flow_compact(steps: list[FlowStep]) -> str:
    """Format flow steps as a compact tree with box-drawing characters.

    Each step is rendered on one line.  Depth-0 is the root (no prefix),
    deeper levels use box-drawing connectors with
    indentation proportional to depth.

    Args:
        steps: Ordered list of FlowSteps (BFS order, ascending depth).

    Returns:
        Tree-formatted string.  Empty string when *steps* is empty.
    """
    if not steps:
        return ""

    lines: list[str] = []
    for i, step in enumerate(steps):
        resolved = f" \u2192 {step.resolved_module}" if step.resolved_module else ""
        loc = f"  ({step.module}:{step.line}{resolved})" if step.module else ""
        if step.depth == 0:
            lines.append(step.name + loc)
            continue

        # Determine if this is the last sibling at its depth
        is_last = True
        for j in range(i + 1, len(steps)):
            if steps[j].depth < step.depth:
                break
            if steps[j].depth == step.depth:
                is_last = False
                break

        # Indent: 4 spaces per ancestor level above depth 0
        indent = "    " * (step.depth - 1)
        connector = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
        lines.append(indent + connector + step.name + loc)

    return "\n".join(lines)
