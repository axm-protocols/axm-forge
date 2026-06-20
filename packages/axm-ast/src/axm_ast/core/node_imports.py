"""ES6/TypeScript import resolution and node dependency-edge construction.

Python imports are near-literal (a dotted name maps almost directly to a path);
ES6 imports are paths that must be *resolved* against the filesystem the way
Node/TypeScript do it:

* **relative** (``"./util.js"``, ``"../lib/x"``) → resolved against the importer's
  directory. TS keeps the ``.js`` extension in source even though the real file
  is ``.ts`` (``allowImportingTsExtensions`` / NodeNext), so we try the TS
  extensions and an ``index.*`` directory fallback.
* **bare specifier** (``"react"``, ``"lodash"``) → an external npm package under
  ``node_modules/``; never an internal edge.
* **alias** (``"$lib/…"``, ``"@/…"``) → defined in tsconfig/vite config; resolving
  these needs the config and is out of scope here (treated as external).

Only *internal* relative imports that resolve to another module in the package
produce a dependency edge, matching the Python ``_build_edges`` contract:
``(src_module_name, target_module_name)`` where the name is the module's path
relative to the package root.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from axm_ast.models.nodes import ImportInfo, ModuleInfo

__all__ = ["node_module_name", "resolve_node_edges"]

# Extensions a TS import may actually resolve to, in priority order.
_RESOLVE_EXTS = (".ts", ".tsx", ".js", ".jsx")
# Directory-import index files, in priority order.
_INDEX_NAMES = ("index.ts", "index.tsx", "index.js", "index.jsx")


def node_module_name(path: Path, root: Path) -> str:
    """Return a node module's stable name: its path relative to *root* (POSIX).

    Unlike Python's dotted name, a TS module has no package-qualified identity;
    its path relative to the package root is the unique, readable key used on
    both ends of a dependency edge.
    """
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _strip_source_ext(spec: str) -> str:
    """Drop a trailing source extension from an import specifier.

    ``"./util.js"`` → ``"./util"`` so the extension-probing below can try the
    real on-disk extensions (TS authors write ``.js`` for a ``.ts`` file).
    """
    for ext in (".js", ".jsx", ".ts", ".tsx"):
        if spec.endswith(ext):
            return spec[: -len(ext)]
    return spec


def _resolve_relative(spec: str, importer: Path) -> Path | None:
    """Resolve a relative import *spec* from *importer* to a real file, or None.

    Tries, in order: the exact path with each TS extension, then an ``index.*``
    file if the spec points at a directory.
    """
    base = (importer.parent / _strip_source_ext(spec)).resolve()

    for ext in _RESOLVE_EXTS:
        candidate = base.with_name(base.name + ext)
        if candidate.is_file():
            return candidate

    if base.is_dir():
        for index_name in _INDEX_NAMES:
            candidate = base / index_name
            if candidate.is_file():
                return candidate
    return None


def _is_relative_spec(imp: ImportInfo) -> bool:
    """Return True if *imp* is a relative import (resolvable to a local file)."""
    module = imp.module or ""
    return imp.is_relative or module.startswith(".")


def resolve_node_edges(modules: list[ModuleInfo], root: Path) -> list[tuple[str, str]]:
    """Build internal dependency edges for a node package by resolving imports.

    For each module, every relative import is resolved against the filesystem;
    when it lands on another module of the package, a ``(src, target)`` edge is
    emitted (both endpoints named by :func:`node_module_name`). Bare specifiers
    (npm packages) and unresolved aliases are skipped — they are not internal.

    Args:
        modules: The package's parsed modules.
        root: The package root the names are relative to.

    Returns:
        Sorted, de-duplicated list of internal dependency edges.
    """
    known: dict[Path, str] = {
        mod.path.resolve(): node_module_name(mod.path, root) for mod in modules
    }
    edges: set[tuple[str, str]] = set()

    for mod in modules:
        src_name = known[mod.path.resolve()]
        for imp in mod.imports:
            if not _is_relative_spec(imp) or not imp.module:
                continue
            resolved = _resolve_relative(imp.module, mod.path)
            if resolved is None:
                continue
            target_name = known.get(resolved)
            if target_name is not None and target_name != src_name:
                edges.add((src_name, target_name))

    return sorted(edges)
