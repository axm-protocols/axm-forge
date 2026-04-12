"""High-level package analysis engine.

This module builds on the tree-sitter parser to provide package-wide
analysis: module discovery, dependency graphs, public API extraction,
and semantic search.

Example:
    >>> from pathlib import Path
    >>> from axm_ast.core.analyzer import analyze_package
    >>> pkg = analyze_package(Path("src/mylib"))
    >>> [m.path.name for m in pkg.modules]
    `['__init__.py', 'core.py', 'utils.py']`
"""

from __future__ import annotations

import logging
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from axm_ast.core.parser import extract_module_info
from axm_ast.models.nodes import (
    ClassInfo,
    FunctionInfo,
    FunctionKind,
    ImportInfo,
    ModuleInfo,
    PackageInfo,
    SymbolKind,
    VariableInfo,
)

logger = logging.getLogger(__name__)

__all__ = [
    "analyze_package",
    "build_import_graph",
    "find_module_for_symbol",
    "get_public_api",
    "module_dotted_name",
    "search_symbols",
]

# Directories to skip during file discovery.
_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".venv",
        "venv",
        ".env",
        "env",
        "__pycache__",
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".tox",
        ".nox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".eggs",
    }
)


def analyze_package(path: Path) -> PackageInfo:
    """Analyze a Python package directory.

    Discovers all ``.py`` files, parses them with tree-sitter, and
    builds a complete ``PackageInfo`` with dependency edges.

    Args:
        path: Path to the package root directory.

    Returns:
        PackageInfo with all modules and dependency edges.

    Raises:
        ValueError: If path is not a directory.

    Example:
        >>> pkg = analyze_package(Path("src/mylib"))
        >>> pkg.name
        'mylib'
    """
    path = Path(path).resolve()
    if not path.is_dir():
        msg = f"{path} is not a directory"
        raise ValueError(msg)

    # Detect src-layout: src/<pkg>/__init__.py
    src_dir = path / "src"
    if src_dir.is_dir() and any(
        (child / "__init__.py").exists()
        for child in src_dir.iterdir()
        if child.is_dir()
    ):
        path = src_dir

    t0 = time.perf_counter()

    # Discover all .py files, skipping virtual envs and caches
    py_files = sorted(_discover_py_files(path))
    modules: list[ModuleInfo] = []
    for py_file in py_files:
        modules.append(extract_module_info(py_file))

    # Build dependency edges from internal imports
    dep_edges = _build_edges(modules, path)

    pkg = PackageInfo(
        name=path.name,
        root=path,
        modules=modules,
        dependency_edges=dep_edges,
    )

    elapsed = time.perf_counter() - t0
    logger.debug("Analyzed %s in %.2fs (%d modules)", path.name, elapsed, len(modules))

    return pkg


def _find_git_root(path: Path) -> Path | None:
    """Walk up from *path* to locate the nearest ``.git`` directory."""
    current = path.resolve()
    while True:
        if (current / ".git").is_dir():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def _is_gitignored(path: Path, git_root: Path) -> bool:
    """Return ``True`` if *path* is ignored according to git."""
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", str(path)],
            cwd=git_root,
            capture_output=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _discover_py_files(root: Path) -> list[Path]:
    """Discover ``.py`` files recursively, skipping non-source directories.

    Skips virtual environments, caches, VCS directories, and build
    artifacts defined in ``_SKIP_DIRS``.  Additionally, when inside a
    git repository, directories matched by ``.gitignore`` rules are
    skipped.  Uses ``iterdir()`` instead of ``rglob()`` so that
    skipped subtrees are never entered.

    Args:
        root: Directory to scan.

    Returns:
        List of discovered ``.py`` file paths.
    """
    return _discover_py_files_inner(root, _find_git_root(root))


def _discover_py_files_inner(root: Path, git_root: Path | None) -> list[Path]:
    """Recursive helper for :func:`_discover_py_files`."""
    results: list[Path] = []
    for child in sorted(root.iterdir()):
        if child.is_dir():
            if child.name in _SKIP_DIRS or child.name.endswith(".egg-info"):
                continue
            if git_root is not None and _is_gitignored(child, git_root):
                continue
            results.extend(_discover_py_files_inner(child, git_root))
        elif child.suffix == ".py":
            results.append(child)
    return results


def module_dotted_name(mod_path: Path, root: Path) -> str:
    """Convert a module file path to a dotted name relative to root.

    Args:
        mod_path: Absolute path to a ``.py`` file.
        root: Package root directory.

    Returns:
        Dotted module name (e.g. ``"core.parser"``).
    """
    try:
        rel = mod_path.relative_to(root)
    except ValueError:
        return mod_path.stem
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    if parts and parts[0] == "src" and len(parts) > 1:
        parts = parts[1:]
    return ".".join(parts) if parts else root.name


def find_module_for_symbol(
    pkg: PackageInfo,
    symbol: str | FunctionInfo | ClassInfo | VariableInfo,
) -> ModuleInfo | None:
    """Find the module containing a symbol.

    Supports two lookup modes:

    - **Object** (``FunctionInfo`` / ``ClassInfo``): identity-first match,
      then name fallback.
    - **String**: name-based search across functions, methods, and classes.

    Args:
        pkg: Analyzed package info.
        symbol: Symbol name or object to locate.

    Returns:
        The ``ModuleInfo`` containing the symbol, or ``None``.
    """
    if not isinstance(symbol, str):
        # Identity match (when passed an object)
        result = _find_module_by_identity(pkg, symbol)
        if result is not None:
            return result
        # Fallback to name-based search
        symbol = symbol.name

    return _find_module_by_name(pkg, symbol)


def _search_in_module(
    mod: ModuleInfo,
    predicate: Callable[[FunctionInfo | ClassInfo | VariableInfo], bool],
) -> bool:
    """Check whether *mod* contains a symbol satisfying *predicate*."""
    if any(predicate(fn) for fn in mod.functions):
        return True
    for cls in mod.classes:
        if predicate(cls):
            return True
        if any(predicate(m) for m in cls.methods):
            return True
    return any(predicate(v) for v in mod.variables)


def _find_module_by_identity(
    pkg: PackageInfo,
    sym: FunctionInfo | ClassInfo | VariableInfo,
) -> ModuleInfo | None:
    """Find module by object identity (``is`` comparison)."""
    for mod in pkg.modules:
        if _search_in_module(mod, lambda s: s is sym):
            return mod
    return None


def _find_module_by_name(
    pkg: PackageInfo,
    name: str,
) -> ModuleInfo | None:
    """Find module by symbol name (first match)."""
    for mod in pkg.modules:
        if _search_in_module(mod, lambda s: s.name == name):
            return mod
    return None


def _build_edges(modules: list[ModuleInfo], root: Path) -> list[tuple[str, str]]:
    """Build internal import dependency edges."""
    path_to_name: dict[Path, str] = {}
    for mod in modules:
        path_to_name[mod.path] = module_dotted_name(mod.path, root)

    known_names = set(path_to_name.values())
    edges: list[tuple[str, str]] = []

    for mod in modules:
        src_name = path_to_name[mod.path]
        for imp in mod.imports:
            target = _resolve_import_target(imp, mod, root, known_names, src_name)
            if target is not None:
                edges.append((src_name, target))

    return edges


def _resolve_absolute_import(
    module: str,
    pkg_name: str,
    known_names: set[str],
    src_name: str,
) -> str | None:
    """Resolve an absolute import to an internal module name, if applicable."""
    if module.startswith(pkg_name + "."):
        internal = module[len(pkg_name) + 1 :]
        if internal in known_names and internal != src_name:
            return internal
    elif module == pkg_name and pkg_name in known_names and pkg_name != src_name:
        return pkg_name
    return None


def _resolve_import_target(
    imp: ImportInfo,
    mod: ModuleInfo,
    root: Path,
    known_names: set[str],
    src_name: str,
) -> str | None:
    """Resolve an import to a target module name, if internal."""
    if not imp.is_relative:
        if imp.module:
            return _resolve_absolute_import(
                imp.module,
                root.name,
                known_names,
                src_name,
            )
        return None

    if imp.module:
        return imp.module if imp.module in known_names else None

    # from . import X — importing from parent package
    parent_name = module_dotted_name(mod.path.parent / "__init__.py", root)
    if parent_name in known_names and parent_name != src_name:
        return parent_name
    return None


def build_import_graph(pkg: PackageInfo) -> dict[str, list[str]]:
    """Build an adjacency-list import graph from package info.

    Args:
        pkg: Analyzed package info.

    Returns:
        Dict mapping module name to list of modules it imports.

    Example:
        >>> graph = build_import_graph(pkg)
        >>> graph["cli"]
        `['core', 'models']`
    """
    graph: dict[str, list[str]] = {}
    for src, target in pkg.dependency_edges:
        graph.setdefault(src, []).append(target)
    return graph


def get_public_api(pkg: PackageInfo) -> list[FunctionInfo | ClassInfo]:
    """Extract the public API surface of a package.

    Uses ``__all__`` when available, otherwise filters by name convention.

    Args:
        pkg: Analyzed package info.

    Returns:
        List of public functions and classes.

    Example:
        >>> api = get_public_api(pkg)
        >>> [a.name for a in api]
        `['main', 'Config']`
    """
    return pkg.public_api


def search_symbols(
    pkg: PackageInfo,
    *,
    name: str | None = None,
    returns: str | None = None,
    kind: SymbolKind | None = None,
    inherits: str | None = None,
) -> list[tuple[str, FunctionInfo | ClassInfo | VariableInfo]]:
    """Search for symbols across a package with filters.

    All filters are AND-combined. A symbol must match all provided
    filters to be included in results.

    Args:
        pkg: Analyzed package info.
        name: Filter by symbol name (substring match).
        returns: Filter functions by return type (substring match).
        kind: Filter by SymbolKind (function, method, property,
            classmethod, staticmethod, abstract, class, variable).
        inherits: Filter classes by base class name.

    Returns:
        List of (module_name, symbol) tuples for matching symbols.

    Example:
        >>> results = search_symbols(pkg, returns="str")
        >>> [sym.name for _, sym in results]
        `['greet', 'version']`
    """
    results: list[tuple[str, FunctionInfo | ClassInfo | VariableInfo]] = []

    for mod in pkg.modules:
        mod_dotted = mod.name or module_dotted_name(mod.path, pkg.root)
        for sym in _search_module(
            mod,
            name=name,
            returns=returns,
            kind=kind,
            inherits=inherits,
        ):
            results.append((mod_dotted, sym))

    return results


def _search_module(
    mod: ModuleInfo,
    *,
    name: str | None,
    returns: str | None,
    kind: SymbolKind | None,
    inherits: str | None,
) -> list[FunctionInfo | ClassInfo | VariableInfo]:
    """Search for symbols within a single module."""
    if inherits is not None:
        return _search_by_inheritance(mod, name, inherits, kind)

    match kind:
        case SymbolKind.VARIABLE:
            return [] if returns is not None else _search_variables(mod, name=name)
        case SymbolKind.CLASS:
            return [] if returns is not None else _search_classes_only(mod, name=name)
        case None:
            return _search_all(mod, name=name, returns=returns)
        case _:
            fn_kind = FunctionKind(kind.value)
            return _search_by_function_kind(
                mod, name=name, returns=returns, fn_kind=fn_kind
            )


def _search_all(
    mod: ModuleInfo,
    *,
    name: str | None,
    returns: str | None,
) -> list[FunctionInfo | ClassInfo | VariableInfo]:
    """Search all symbol types (no kind filter)."""
    results: list[FunctionInfo | ClassInfo | VariableInfo] = []
    for fn in mod.functions:
        if _match_function(fn, name=name, returns=returns):
            results.append(fn)
    results.extend(_search_classes(mod, name=name, returns=returns, kind=None))
    results.extend(_search_variables(mod, name=name))
    return results


def _search_by_function_kind(
    mod: ModuleInfo,
    *,
    name: str | None,
    returns: str | None,
    fn_kind: FunctionKind,
) -> list[FunctionInfo | ClassInfo | VariableInfo]:
    """Search top-level functions and class methods for a specific function kind."""
    results: list[FunctionInfo | ClassInfo | VariableInfo] = []
    for fn in mod.functions:
        if _match_function(fn, name=name, returns=returns, kind=fn_kind):
            results.append(fn)
    for cls in mod.classes:
        for method in cls.methods:
            if _match_function(method, name=name, returns=returns, kind=fn_kind):
                results.append(method)
    return results


def _search_classes_only(
    mod: ModuleInfo,
    *,
    name: str | None,
) -> list[FunctionInfo | ClassInfo | VariableInfo]:
    """Return only classes, optionally filtered by name."""
    results: list[FunctionInfo | ClassInfo | VariableInfo] = []
    for cls in mod.classes:
        if name is None or name in cls.name:
            results.append(cls)
    return results


def _search_variables(
    mod: ModuleInfo,
    *,
    name: str | None,
) -> list[FunctionInfo | ClassInfo | VariableInfo]:
    """Return module-level variables, optionally filtered by name."""
    results: list[FunctionInfo | ClassInfo | VariableInfo] = []
    for var in mod.variables:
        if name is None or name in var.name:
            results.append(var)
    return results


def _search_by_inheritance(
    mod: ModuleInfo,
    name: str | None,
    inherits: str,
    kind: SymbolKind | None = None,
) -> list[FunctionInfo | ClassInfo | VariableInfo]:
    """Search classes by base class inheritance."""
    # If kind is set and is not CLASS, no class can match
    if kind is not None and kind != SymbolKind.CLASS:
        return []
    results: list[FunctionInfo | ClassInfo | VariableInfo] = []
    for cls in mod.classes:
        if inherits in cls.bases and (name is None or name in cls.name):
            results.append(cls)
    return results


def _search_classes(
    mod: ModuleInfo,
    *,
    name: str | None,
    returns: str | None,
    kind: FunctionKind | None,
) -> list[FunctionInfo | ClassInfo]:
    """Search classes and their methods for matching symbols."""
    results: list[FunctionInfo | ClassInfo] = []
    for cls in mod.classes:
        if name is not None and name in cls.name:
            results.append(cls)
            continue
        for method in cls.methods:
            if _match_function(method, name=name, returns=returns, kind=kind):
                results.append(method)
    return results


def _match_function(
    fn: FunctionInfo,
    *,
    name: str | None = None,
    returns: str | None = None,
    kind: FunctionKind | None = None,
) -> bool:
    """Check if a function matches the given filters."""
    if name is not None and name not in fn.name:
        return False
    if returns is not None:
        if fn.return_type is None or returns not in fn.return_type:
            return False
    if kind is not None and fn.kind != kind:
        return False
    return True
