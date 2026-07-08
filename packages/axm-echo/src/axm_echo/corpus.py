"""Corpus extractor -- public symbols + their embeddable text.

Ported from the POC ``docstring_corpus.py``, but rebranched onto
**axm-ast** (tree-sitter) instead of the stdlib ``ast`` module: symbols,
signatures, and docstrings now come from ``axm_ast.core.parser`` and the
first docstring line from ``axm_ast.docstring_parser.parse_docstring``.

The unified embedding text (AC3) is, per symbol::

    embed_text = docstring if present else signature

so a public documented symbol contributes its intent while an
undocumented one still contributes its *signature* (``body_norm`` holds the
signature, not a normalized body -- bodies are not extracted). One engine,
one vector space, the registry picked per symbol.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from axm_ast.core.parser import extract_module_info
from axm_ast.docstring_parser import parse_docstring

from axm_echo.scope import load_scope

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from axm_ast.models.nodes import ClassInfo, FunctionInfo, ModuleInfo

__all__ = [
    "Symbol",
    "SymbolDict",
    "discover_package_roots",
    "extract_monorepo",
    "extract_package",
]

# Public symbol record: a flat, JSON-friendly mapping keyed by field name
# (qualname, package, signature, doc_first_line, doc_full, body_norm,
# embed_text, ...). The extractors emit these dicts (AC3); ``Symbol`` is
# the internal builder behind them.
type SymbolDict = dict[str, str | int | bool]


@dataclass(frozen=True)
class Symbol:
    """A single public symbol projected into the corpus."""

    qualname: str
    name: str
    package: str
    workspace: str
    kind: str  # "function" | "class"
    signature: str
    doc_first_line: str
    doc_full: str
    body_norm: str
    path: str
    line: int

    @property
    def has_doc(self) -> bool:
        """Whether the symbol carries a non-empty docstring."""
        return bool(self.doc_full.strip())

    @property
    def embed_text(self) -> str:
        """Unified embed text: docstring if present, else code/signature."""
        if self.doc_full.strip():
            return f"{self.signature}\n{self.doc_full}".strip()
        return f"{self.signature}\n{self.body_norm}".strip()

    def as_dict(self) -> SymbolDict:
        """Flat dict view (qualname, package, signature, embed_text, ...)."""
        return {
            "qualname": self.qualname,
            "name": self.name,
            "package": self.package,
            "workspace": self.workspace,
            "kind": self.kind,
            "signature": self.signature,
            "doc_first_line": self.doc_first_line,
            "doc_full": self.doc_full,
            "body_norm": self.body_norm,
            "embed_text": self.embed_text,
            "has_doc": self.has_doc,
            "path": self.path,
            "line": self.line,
        }


def _package_meta(pkg_root: Path) -> tuple[str, str]:
    """(package, workspace) from a ``<ws>/packages/<pkg>`` or ``other/`` layout."""
    package = pkg_root.name
    workspace = "?"
    parts = pkg_root.parts
    if "packages" in parts:
        idx = parts.index("packages")
        if idx >= 1:
            workspace = parts[idx - 1]
    elif "other" in parts:
        workspace = "other"
    return package, workspace


def _first_doc_line(docstring: str | None) -> str:
    """First line of the docstring summary via axm-ast's parser."""
    parsed = parse_docstring(docstring)
    summary = parsed.summary or ""
    first = summary.strip().splitlines()
    return first[0].strip() if first else ""


#: Path segments whose subtrees never contain first-party source: test
#: trees plus vendored / generated artefacts (a committed ``.venv``,
#: caches, JS deps, build outputs). Matched on whole path *segments*
#: (``in py.parts``), never as substrings — so a legitimate package such
#: as ``buildkit`` is not excluded by the ``build`` entry.
_EXCLUDED_SEGMENTS: frozenset[str] = frozenset(
    {
        "tests",
        ".venv",
        "venv",
        "site-packages",
        "__pycache__",
        "node_modules",
        ".tox",
        "build",
        "dist",
        ".git",
    }
)


def _iter_source_files(pkg_root: Path) -> Iterator[Path]:
    """Yield parseable, non-test source files of a package.

    Any file under an excluded segment (``tests``, ``.venv``,
    ``site-packages``, ``__pycache__``, build/vendored trees — see
    :data:`_EXCLUDED_SEGMENTS`) is skipped so third-party libraries living
    inside a committed virtualenv never leak into the corpus.
    """
    src = pkg_root / "src"
    search_root = src if src.exists() else pkg_root
    for py in sorted(search_root.rglob("*.py")):
        if _EXCLUDED_SEGMENTS.intersection(py.parts):
            continue
        try:
            is_empty_init = py.name == "__init__.py" and py.stat().st_size == 0
        except OSError:
            # A broken symlink or a file removed mid-walk must not abort the
            # whole extraction: honour the "unparseable files are silently
            # ignored" contract and skip it.
            continue
        if is_empty_init:
            continue
        yield py


def _module_qualname(py: Path, pkg_root: Path) -> str:
    """Dotted module path relative to the package's source root."""
    src = pkg_root / "src"
    search_root = src if src.exists() else pkg_root
    return ".".join(py.relative_to(search_root).with_suffix("").parts)


def _function_symbol(
    fn: FunctionInfo, mod_qual: str, py: Path, package: str, workspace: str
) -> Symbol:
    doc = fn.docstring or ""
    return Symbol(
        qualname=f"{mod_qual}.{fn.name}",
        name=fn.name,
        package=package,
        workspace=workspace,
        kind="function",
        signature=fn.signature or f"def {fn.name}(...)",
        doc_first_line=_first_doc_line(fn.docstring),
        doc_full=doc.strip(),
        body_norm=(fn.signature or ""),
        path=str(py),
        line=fn.line_start,
    )


def _class_symbol(
    cls: ClassInfo, mod_qual: str, py: Path, package: str, workspace: str
) -> Symbol:
    doc = cls.docstring or ""
    bases = f"({', '.join(cls.bases)})" if cls.bases else ""
    return Symbol(
        qualname=f"{mod_qual}.{cls.name}",
        name=cls.name,
        package=package,
        workspace=workspace,
        kind="class",
        signature=f"class {cls.name}{bases}",
        doc_first_line=_first_doc_line(cls.docstring),
        doc_full=doc.strip(),
        body_norm="",
        path=str(py),
        line=cls.line_start,
    )


def _module_symbols(
    mod: ModuleInfo, mod_qual: str, py: Path, package: str, workspace: str
) -> list[Symbol]:
    symbols: list[Symbol] = []
    for fn in mod.public_functions:
        symbols.append(_function_symbol(fn, mod_qual, py, package, workspace))
    for cls in mod.public_classes:
        symbols.append(_class_symbol(cls, mod_qual, py, package, workspace))
    return symbols


def extract_package(pkg_root: Path) -> list[SymbolDict]:
    """Extract every public function/class of a package via axm-ast.

    "Public" follows the axm-ast convention: a symbol exported in the
    module's ``__all__`` when present, else any module-level name without
    a leading underscore. Test files and empty ``__init__`` files are
    skipped; unparseable files are silently ignored.

    Args:
        pkg_root: Package directory (containing ``src/<pkg>/`` or a flat
            source tree).

    Returns:
        One ``Symbol`` per public function/class, each carrying
        ``qualname``, ``signature``, ``doc_first_line``, ``doc_full``,
        ``body_norm`` (the signature, used as the fallback embed text for
        undocumented symbols -- bodies are not extracted) and the derived
        ``embed_text``.
    """
    package, workspace = _package_meta(pkg_root)
    symbols: list[Symbol] = []
    for py in _iter_source_files(pkg_root):
        try:
            mod = extract_module_info(py)
        except (OSError, ValueError):
            continue
        mod_qual = _module_qualname(py, pkg_root)
        symbols.extend(_module_symbols(mod, mod_qual, py, package, workspace))
    return [s.as_dict() for s in symbols]


def discover_package_roots() -> list[Path]:
    """Discover every package directory across the configured scope.

    Walks each workspace root from :func:`axm_echo.scope.load_scope`,
    covering both the ``<ws>/packages/<pkg>`` convention and the flat
    ``other/<pkg>`` layout. The set of roots is data-driven (no frozen
    package list), so newly added packages are picked up automatically
    (AC4).

    Returns:
        Sorted, de-duplicated package directories.
    """
    seen: set[Path] = set()
    roots: list[Path] = []
    for workspace_root in load_scope():
        for pkg in _packages_in_workspace(workspace_root):
            if pkg not in seen:
                seen.add(pkg)
                roots.append(pkg)
    return sorted(roots)


def _packages_in_workspace(workspace_root: Path) -> Iterator[Path]:
    """Yield package dirs under one workspace root (or the root itself).

    The scope (``~/.axm/config.toml`` ``[echo]``) lists *workspace roots
    directly*, so
    packages live one level below the root. Handles, off the workspace root:
      - ``<workspace_root>/packages/<pkg>`` (the AXM monorepo convention)
      - ``<workspace_root>/other/<pkg>`` (the ``other`` subdir as a flat
        container of packages)
      - ``<workspace_root>/<pkg>`` (flat: the root itself holds packages as
        direct children, e.g. when the ``other`` dir is listed as a root)
    Falls back to the workspace root as a single package when it exposes no
    recognisable package directory.
    """
    if not workspace_root.is_dir():
        return
    found = False
    for container in (workspace_root / "packages", workspace_root / "other"):
        if container.is_dir():
            for pkg in sorted(container.iterdir()):
                if _is_package_dir(pkg):
                    found = True
                    yield pkg
    # Flat layout: a root (e.g. ``other`` listed directly) that holds packages
    # as direct children. Harmless for a monorepo root, whose direct children
    # (``packages``, ``other``, ``docs``, ``.github`` …) are not package dirs.
    for child in sorted(workspace_root.iterdir()):
        if child.name not in {"packages", "other"} and _is_package_dir(child):
            found = True
            yield child
    if not found and _is_package_dir(workspace_root):
        yield workspace_root


def _is_package_dir(path: Path) -> bool:
    """Whether ``path`` looks like an extractable package.

    Requires a genuine package marker — a ``src/`` directory OR a
    ``pyproject.toml`` — so doc dirs and folders holding a stray ``*.py``
    (e.g. ``docs/gen_ref_pages.py``) are not mistaken for packages (AC4).
    """
    if not path.is_dir():
        return False
    return (path / "src").is_dir() or (path / "pyproject.toml").is_file()


def extract_monorepo() -> list[SymbolDict]:
    """Extract public symbols across every discovered package (corpus).

    Returns:
        The concatenated symbol corpus for the configured scope.
    """
    out: list[SymbolDict] = []
    for pkg in discover_package_roots():
        out.extend(extract_package(pkg))
    return out
