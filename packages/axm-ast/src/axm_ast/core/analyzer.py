"""High-level package analysis engine.

This module builds on the tree-sitter parser to provide package-wide
analysis: module discovery, dependency graphs, public API extraction,
semantic search, and stub generation.

Example:
    >>> from pathlib import Path
    >>> from axm_ast.core.analyzer import analyze_package
    >>> pkg = analyze_package(Path("src/mylib"))
    >>> [m.path.name for m in pkg.modules]
    ['__init__.py', 'core.py', 'utils.py']
"""

from __future__ import annotations

from pathlib import Path

from axm_ast.core.parser import extract_module_info
from axm_ast.models.nodes import (
    ClassInfo,
    FunctionInfo,
    FunctionKind,
    ImportInfo,
    ModuleInfo,
    PackageInfo,
)

__all__ = [
    "analyze_package",
    "build_import_graph",
    "generate_stubs",
    "get_public_api",
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

    # Discover all .py files, skipping virtual envs and caches
    py_files = sorted(_discover_py_files(path))
    modules: list[ModuleInfo] = []
    for py_file in py_files:
        modules.append(extract_module_info(py_file))

    # Build dependency edges from internal imports
    dep_edges = _build_edges(modules, path)

    return PackageInfo(
        name=path.name,
        root=path,
        modules=modules,
        dependency_edges=dep_edges,
    )


def _discover_py_files(root: Path) -> list[Path]:
    """Discover ``.py`` files recursively, skipping non-source directories.

    Skips virtual environments, caches, VCS directories, and build
    artifacts defined in ``_SKIP_DIRS``.  Uses ``iterdir()`` instead
    of ``rglob()`` so that skipped subtrees are never entered.

    Args:
        root: Directory to scan.

    Returns:
        List of discovered ``.py`` file paths.
    """
    results: list[Path] = []
    for child in sorted(root.iterdir()):
        if child.is_dir():
            if child.name in _SKIP_DIRS or child.name.endswith(".egg-info"):
                continue
            results.extend(_discover_py_files(child))
        elif child.suffix == ".py":
            results.append(child)
    return results


def _module_dotted_name(mod_path: Path, root: Path) -> str:
    """Convert a module file path to a dotted name relative to root."""
    try:
        rel = mod_path.relative_to(root)
    except ValueError:
        return mod_path.stem
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else root.name


def _build_edges(modules: list[ModuleInfo], root: Path) -> list[tuple[str, str]]:
    """Build internal import dependency edges."""
    path_to_name: dict[Path, str] = {}
    for mod in modules:
        path_to_name[mod.path] = _module_dotted_name(mod.path, root)

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
    parent_name = _module_dotted_name(mod.path.parent / "__init__.py", root)
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
        ['core', 'models']
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
        ['main', 'Config']
    """
    return pkg.public_api


def search_symbols(
    pkg: PackageInfo,
    *,
    name: str | None = None,
    returns: str | None = None,
    kind: FunctionKind | None = None,
    inherits: str | None = None,
) -> list[FunctionInfo | ClassInfo]:
    """Search for symbols across a package with filters.

    All filters are AND-combined. A symbol must match all provided
    filters to be included in results.

    Args:
        pkg: Analyzed package info.
        name: Filter by symbol name (substring match).
        returns: Filter functions by return type (substring match).
        kind: Filter functions by FunctionKind.
        inherits: Filter classes by base class name.

    Returns:
        List of matching symbols.

    Example:
        >>> results = search_symbols(pkg, returns="str")
        >>> [r.name for r in results]
        ['greet', 'version']
    """
    results: list[FunctionInfo | ClassInfo] = []

    for mod in pkg.modules:
        results.extend(
            _search_module(
                mod,
                name=name,
                returns=returns,
                kind=kind,
                inherits=inherits,
            )
        )

    return results


def _search_module(
    mod: ModuleInfo,
    *,
    name: str | None,
    returns: str | None,
    kind: FunctionKind | None,
    inherits: str | None,
) -> list[FunctionInfo | ClassInfo]:
    """Search for symbols within a single module."""
    if inherits is not None:
        return _search_by_inheritance(mod, name, inherits)

    results: list[FunctionInfo | ClassInfo] = []
    for fn in mod.functions:
        if _match_function(fn, name=name, returns=returns, kind=kind):
            results.append(fn)

    results.extend(_search_classes(mod, name=name, returns=returns, kind=kind))
    return results


def _search_by_inheritance(
    mod: ModuleInfo, name: str | None, inherits: str
) -> list[FunctionInfo | ClassInfo]:
    """Search classes by base class inheritance."""
    results: list[FunctionInfo | ClassInfo] = []
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


def generate_stubs(pkg: PackageInfo) -> str:
    """Generate compact ``.pyi``-like stub output for a package.

    Produces a minimal interface summary that shows only signatures,
    docstring first lines, and class/function structure — no implementation.

    Args:
        pkg: Analyzed package info.

    Returns:
        Stub text as a single string.

    Example:
        >>> print(generate_stubs(pkg))
        # sample_pkg/__init__.py
        def greet(name: str = "world") -> str: ...
        class Calculator: ...
    """
    lines: list[str] = []

    for mod in pkg.modules:
        mod_name = _module_dotted_name(mod.path, pkg.root)
        lines.append(f"# {mod_name}")
        if mod.docstring:
            first_line = mod.docstring.strip().split("\n")[0]
            lines.append(f'"""{first_line}"""')
        lines.append("")

        for fn in mod.functions:
            lines.append(_stub_function(fn, indent=0))

        for cls in mod.classes:
            lines.append(_stub_class(cls))

        lines.append("")

    return "\n".join(lines)


def _stub_function(fn: FunctionInfo, indent: int = 0) -> str:
    """Generate a stub line for a function."""
    prefix = "    " * indent
    return f"{prefix}{fn.signature}: ..."


def _stub_class(cls: ClassInfo) -> str:
    """Generate stub lines for a class."""
    bases_str = f"({', '.join(cls.bases)})" if cls.bases else ""
    lines = [f"class {cls.name}{bases_str}:"]
    if cls.docstring:
        first_line = cls.docstring.strip().split("\n")[0]
        lines.append(f'    """{first_line}"""')
    if cls.methods:
        for method in cls.methods:
            lines.append(_stub_function(method, indent=1))
    else:
        lines.append("    ...")
    return "\n".join(lines)
