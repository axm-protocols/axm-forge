"""Caller rewriting: redirect ``from old_module import Symbol`` to ``new_module``."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import libcst as cst
from libcst.codemod import CodemodContext
from libcst.codemod.visitors import AddImportsVisitor

from axm_anvil._cst.transformers import AttributeRewriter

__all__ = [
    "CallerRewrite",
    "_discover_callers",
    "_discover_module_import_callers",
    "_module_path_from_file",
    "_rewrite_module_import_caller",
    "rewrite_caller_text",
]


@dataclass
class CallerRewrite:
    """A single caller-import rewrite record for :class:`MovePlan`."""

    file: str
    line: int
    old: str
    new: str


def _dump_module(node: cst.BaseExpression | None) -> str:
    if node is None:
        return ""
    if isinstance(node, cst.Attribute):
        return f"{_dump_module(node.value)}.{node.attr.value}"
    if isinstance(node, cst.Name):
        return node.value
    return ""


def _package_root_of(file_path: Path, workspace_root: Path) -> Path | None:
    """Return the topmost ``__init__.py``-bearing ancestor under the workspace.

    This is the importable-package root: the highest directory that still
    holds an ``__init__.py`` while remaining an ancestor of ``file_path`` and
    under ``workspace_root``. For a ``packages/pkg/src/pkg/mod.py`` monorepo
    layout it resolves to ``.../src/pkg`` (``src`` has no ``__init__.py``),
    so the derived dotted path is the real import path ``pkg.mod`` rather
    than the on-disk ``packages.pkg.src.pkg.mod``.
    """
    current = file_path.resolve().parent
    root_resolved = workspace_root.resolve()
    if root_resolved not in {current, *current.parents}:
        return None
    result: Path | None = None
    while True:
        if (current / "__init__.py").is_file():
            result = current
        if current == root_resolved:
            break
        parent = current.parent
        if parent == current:
            break
        current = parent
    return result


def _module_path_from_file(file_path: Path, workspace_root: Path) -> str:
    """Derive the dotted *import* path for ``file_path`` under ``workspace_root``.

    Resolves the importable-package root (topmost ``__init__.py`` ancestor)
    and derives the dotted path relative to that root's parent, so a monorepo
    ``packages/pkg/src/pkg/mod.py`` layout yields ``pkg.mod`` — the path that
    real callers actually ``import`` — not the on-disk
    ``packages.pkg.src.pkg.mod`` that never matches an import statement.

    Falls back to the workspace-relative path (stripping a leading ``src/``)
    when no package root can be found (e.g. a top-level flat module).
    """
    resolved = file_path.resolve()
    pkg_root = _package_root_of(resolved, workspace_root)
    if pkg_root is not None:
        rel = resolved.relative_to(pkg_root.parent)
        parts = list(rel.with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        return ".".join(parts)
    rel = resolved.relative_to(workspace_root.resolve())
    parts = list(rel.with_suffix("").parts)
    if parts and parts[0] == "src":
        parts = parts[1:]
    return ".".join(parts)


class _CollectOldImport(cst.CSTVisitor):
    """Record the aliases of moved names imported from ``old_module``."""

    def __init__(self, old_module: str, moved_names: set[str]) -> None:
        super().__init__()
        self._old_module = old_module
        self._moved_names = moved_names
        self.matched_names: dict[str, str | None] = {}
        self.original_line: str | None = None

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:  # noqa: N802
        """Capture asnames and the original text for matching ImportFroms."""
        if _dump_module(node.module) != self._old_module:
            return
        if isinstance(node.names, cst.ImportStar):
            return
        for alias in node.names:
            raw_name = alias.name.value
            if not isinstance(raw_name, str):
                continue
            if raw_name in self._moved_names:
                asname = alias.asname.name.value if alias.asname else None  # type: ignore[union-attr]
                self.matched_names[raw_name] = (
                    asname if isinstance(asname, str) else None
                )


class _RewriteOldImport(cst.CSTTransformer):
    """Remove ``moved_names`` from ``from old_module import …`` lines."""

    def __init__(self, old_module: str, moved_names: set[str]) -> None:
        super().__init__()
        self._old_module = old_module
        self._moved_names = moved_names
        self.touched_lines: list[int] = []

    def leave_ImportFrom(  # noqa: N802
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom | cst.RemovalSentinel:
        """Remove matching names from the import; drop the line if none remain."""
        if _dump_module(updated_node.module) != self._old_module:
            return updated_node
        if isinstance(updated_node.names, cst.ImportStar):
            return updated_node
        if not any(a.name.value in self._moved_names for a in updated_node.names):
            return updated_node
        kept = [a for a in updated_node.names if a.name.value not in self._moved_names]
        if not kept:
            return cst.RemoveFromParent()
        kept[-1] = kept[-1].with_changes(comma=cst.MaybeSentinel.DEFAULT)
        return updated_node.with_changes(names=kept)


class _ImportFromLocator(cst.CSTVisitor):
    """Locate ``from old_module import …`` lines that bind a moved name."""

    METADATA_DEPENDENCIES = (cst.metadata.PositionProvider,)

    def __init__(self, old_module: str, moved_names: set[str]) -> None:
        super().__init__()
        self._old_module = old_module
        self._moved_names = moved_names
        self.locations: list[tuple[int, list[str]]] = []

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:  # noqa: N802
        """Record ``(line, bound_names)`` for a matching import statement."""
        if _dump_module(node.module) != self._old_module:
            return
        if isinstance(node.names, cst.ImportStar):
            return
        bound = [
            alias.name.value
            for alias in node.names
            if isinstance(alias.name.value, str)
            and alias.name.value in self._moved_names
        ]
        if not bound:
            return
        pos = self.get_metadata(cst.metadata.PositionProvider, node)
        self.locations.append((pos.start.line, bound))


def _find_import_lines(
    text: str, old_module: str, names: set[str]
) -> list[tuple[int, str, list[str]]]:
    """Return ``(lineno, line_text, bound_names)`` per matching import line.

    Only ``from old_module import`` statements that actually bind a name in
    ``names`` are returned, ordered by line number. Uses libcst position
    metadata so multi-line imports resolve to their opening line.
    """
    try:
        tree = cst.parse_module(text)
    except cst.ParserSyntaxError:
        return []
    locator = _ImportFromLocator(old_module, names)
    cst.metadata.MetadataWrapper(tree).visit(locator)
    lines = text.splitlines()
    results: list[tuple[int, str, list[str]]] = []
    for lineno, bound in sorted(locator.locations, key=lambda loc: loc[0]):
        line_text = lines[lineno - 1].strip() if 0 < lineno <= len(lines) else ""
        results.append((lineno, line_text, bound))
    return results


def _find_import_line(
    text: str, old_module: str, names: Iterable[str]
) -> tuple[int, str] | None:
    """Return ``(lineno, line_text)`` of the first ``from old_module import`` line
    that binds one of ``names`` (not merely the first from-import in the file)."""
    located = _find_import_lines(text, old_module, set(names))
    if not located:
        return None
    lineno, line_text, _bound = located[0]
    return lineno, line_text


def _add_new_imports(
    symbols: Sequence[str],
    matched_names: Mapping[str, str | None],
    new_module: str,
) -> CodemodContext:
    context = CodemodContext()
    for name in symbols:
        if name not in matched_names:
            continue
        AddImportsVisitor.add_needed_import(
            context,
            new_module,
            name,
            asname=matched_names[name],
        )
    return context


def _format_new_import_stmt(
    symbols: Sequence[str],
    matched_names: Mapping[str, str | None],
    new_module: str,
) -> str:
    ordered = [n for n in symbols if n in matched_names]
    names_piece = ", ".join(
        f"{n} as {matched_names[n]}" if matched_names[n] else n for n in ordered
    )
    return f"from {new_module} import {names_piece}"


def _build_caller_rewrites(
    located_lines: Sequence[tuple[int, str, list[str]]],
    symbols: Sequence[str],
    matched_names: Mapping[str, str | None],
    new_module: str,
) -> list[CallerRewrite]:
    """Build one :class:`CallerRewrite` per matching import line.

    Each record reflects only the names bound on its own line, so a file with
    several distinct ``from old_module import`` statements yields one record per
    statement rather than a single collapsed entry.
    """
    if not located_lines:
        new_stmt = _format_new_import_stmt(symbols, matched_names, new_module)
        return [CallerRewrite(file="", line=1, old="", new=new_stmt)]
    rewrites: list[CallerRewrite] = []
    for lineno, line_text, bound in located_lines:
        line_matched = {n: matched_names[n] for n in bound if n in matched_names}
        line_symbols = [s for s in symbols if s in line_matched]
        new_stmt = _format_new_import_stmt(line_symbols, line_matched, new_module)
        rewrites.append(
            CallerRewrite(file="", line=lineno, old=line_text, new=new_stmt)
        )
    return rewrites


def rewrite_caller_text(
    text: str,
    old_module: str,
    new_module: str,
    symbols: Sequence[str],
) -> tuple[str, list[CallerRewrite]]:
    """Rewrite ``from old_module import <symbols>`` to ``new_module``.

    Returns ``(new_text, rewrites)``. When no matching import exists the
    original text and an empty list are returned unchanged.
    """
    moved = set(symbols)
    tree = cst.parse_module(text)

    collector = _CollectOldImport(old_module, moved)
    tree.visit(collector)
    if not collector.matched_names:
        return text, []

    new_tree = tree.visit(_RewriteOldImport(old_module, moved))

    context = _add_new_imports(symbols, collector.matched_names, new_module)
    final_tree = AddImportsVisitor(context).transform_module(new_tree)

    located_lines = _find_import_lines(text, old_module, moved)
    rewrites = _build_caller_rewrites(
        located_lines, symbols, collector.matched_names, new_module
    )
    return final_tree.code, rewrites


class _CollectModuleImportAliases(cst.CSTVisitor):
    """Collect local names bound by ``import old_module[ as X]`` statements."""

    def __init__(self, old_module: str) -> None:
        super().__init__()
        self._old_module = old_module
        self.aliases: list[str] = []

    def visit_Import(self, node: cst.Import) -> None:  # noqa: N802
        """Record the local name bound for each matching ``old_module`` alias."""
        for alias in node.names:
            if _dump_module(alias.name) != self._old_module:
                continue
            if alias.asname is not None and isinstance(alias.asname.name, cst.Name):
                self.aliases.append(alias.asname.name.value)
            else:
                self.aliases.append(self._old_module)


class _RemoveModuleImports(cst.CSTTransformer):
    """Drop ``import old_module[ as X]`` statements whose local name has no uses."""

    def __init__(self, old_module: str, aliases_to_remove: set[str]) -> None:
        super().__init__()
        self._old_module = old_module
        self._to_remove = aliases_to_remove

    def _alias_removable(self, alias: cst.ImportAlias) -> bool:
        if _dump_module(alias.name) != self._old_module:
            return False
        if alias.asname is not None and isinstance(alias.asname.name, cst.Name):
            local = alias.asname.name.value
        else:
            local = self._old_module
        return local in self._to_remove

    def leave_SimpleStatementLine(  # noqa: N802
        self,
        original_node: cst.SimpleStatementLine,
        updated_node: cst.SimpleStatementLine,
    ) -> cst.SimpleStatementLine | cst.RemovalSentinel:
        """Strip matching aliases from an ``import`` line; drop if all removed."""
        if len(updated_node.body) != 1:
            return updated_node
        inner = updated_node.body[0]
        if not isinstance(inner, cst.Import):
            return updated_node
        kept = [a for a in inner.names if not self._alias_removable(a)]
        if len(kept) == len(inner.names):
            return updated_node
        if not kept:
            return cst.RemoveFromParent()
        kept[-1] = kept[-1].with_changes(comma=cst.MaybeSentinel.DEFAULT)
        return updated_node.with_changes(body=[inner.with_changes(names=kept)])


class _ModuleImportLocator(cst.CSTVisitor):
    """Locate the source line of each ``import old_module[ as X]`` statement."""

    METADATA_DEPENDENCIES = (cst.metadata.PositionProvider,)

    def __init__(self, old_module: str) -> None:
        super().__init__()
        self._old_module = old_module
        self.locations: dict[str, int] = {}

    def visit_Import(self, node: cst.Import) -> None:  # noqa: N802
        """Record ``local_name -> line`` for each matching ``old_module`` alias."""
        pos = self.get_metadata(cst.metadata.PositionProvider, node)
        for alias in node.names:
            if _dump_module(alias.name) != self._old_module:
                continue
            if alias.asname is not None and isinstance(alias.asname.name, cst.Name):
                local = alias.asname.name.value
            else:
                local = self._old_module
            self.locations[local] = pos.start.line


def _line_text_at(text: str, lineno: int) -> str:
    """Return the stripped source line ``lineno`` (1-based) or ``\"\"`` if OOB."""
    lines = text.splitlines()
    if 0 < lineno <= len(lines):
        return lines[lineno - 1].strip()
    return ""


def _build_module_import_rewrites(
    text: str,
    tree: cst.Module,
    old_module: str,
    new_module: str,
    rewritten_aliases: Sequence[str],
) -> list[CallerRewrite]:
    """Build one record per rewritten ``import old_module`` alias.

    Resolves each alias to the real source line and original import text
    (alias-aware) instead of hard-coding ``line=1`` / ``import old_module``.
    """
    locator = _ModuleImportLocator(old_module)
    cst.metadata.MetadataWrapper(tree).visit(locator)
    new_stmt = f"import {new_module}"
    fallback_old = f"import {old_module}"
    rewrites: list[CallerRewrite] = []
    for alias in rewritten_aliases:
        lineno = locator.locations.get(alias)
        if lineno is None:
            rewrites.append(
                CallerRewrite(file="", line=1, old=fallback_old, new=new_stmt)
            )
            continue
        old_text = _line_text_at(text, lineno) or fallback_old
        rewrites.append(CallerRewrite(file="", line=lineno, old=old_text, new=new_stmt))
    return rewrites


def _rewrite_module_import_caller(
    text: str,
    old_module: str,
    new_module: str,
    symbols: Sequence[str],
) -> tuple[str, list[CallerRewrite]]:
    """Rewrite ``old_module.Symbol`` attribute chains via ``import old_module``.

    Returns ``(new_text, rewrites)``. Detects aliases introduced by
    ``import old_module`` or ``import old_module as X``, rewrites all
    ``<alias>.<Symbol>`` chains to ``new_module.<Symbol>``, adds
    ``import new_module`` if any symbol was rewritten, and removes the
    original bare import line when the alias has no residual uses.
    """
    tree = cst.parse_module(text)
    collector = _CollectModuleImportAliases(old_module)
    tree.visit(collector)
    if not collector.aliases:
        return text, []

    moved = set(symbols)
    aliases_to_remove: set[str] = set()
    rewritten_aliases: list[str] = []
    current_tree: cst.Module = tree
    for alias in collector.aliases:
        wrapper = cst.metadata.MetadataWrapper(current_tree)
        rewriter = AttributeRewriter(
            old_module_alias=alias,
            new_module=new_module,
            symbols=moved,
        )
        rewritten = wrapper.visit(rewriter)
        if rewritten.code != current_tree.code:
            rewritten_aliases.append(alias)
        if (
            rewriter.kept_usages == 0
            and rewritten.code != current_tree.code
            and not _alias_used_as_bare_name(rewritten, alias)
        ):
            aliases_to_remove.add(alias)
        current_tree = rewritten

    if not rewritten_aliases:
        return text, []

    context = CodemodContext()
    AddImportsVisitor.add_needed_import(context, new_module)
    current_tree = AddImportsVisitor(context).transform_module(current_tree)

    if aliases_to_remove:
        current_tree = current_tree.visit(
            _RemoveModuleImports(old_module, aliases_to_remove)
        )

    rewrites = _build_module_import_rewrites(
        text, tree, old_module, new_module, rewritten_aliases
    )
    return current_tree.code, rewrites


class _BareNameUsageCounter(cst.CSTVisitor):
    """Count bare-``Name`` uses of ``target`` outside import statements.

    A local alias bound by ``import pkg.old as om`` can survive attribute
    rewriting as a *value* reference (``x = om``). Such a bare use is not an
    ``alias.<attr>`` chain, so :class:`AttributeRewriter` never counts it —
    dropping the import would then leave ``x = om`` dangling (``NameError``).
    This visitor skips ``Import`` / ``ImportFrom`` bodies so only genuine
    value references are counted.
    """

    def __init__(self, target: str) -> None:
        super().__init__()
        self._target = target
        self.count = 0

    def visit_Import(self, node: cst.Import) -> bool:  # noqa: N802
        """Skip ``import`` statements: their names are not value references."""
        return False

    def visit_ImportFrom(self, node: cst.ImportFrom) -> bool:  # noqa: N802
        """Skip ``from`` imports: their names are not value references."""
        return False

    def visit_Attribute(self, node: cst.Attribute) -> bool:  # noqa: N802
        """Skip attribute chains: only the leftmost root is a bare name here."""
        return False

    def visit_Name(self, node: cst.Name) -> None:  # noqa: N802
        """Record a bare-``Name`` occurrence of the alias."""
        if node.value == self._target:
            self.count += 1


def _alias_used_as_bare_name(tree: cst.Module, alias: str) -> bool:
    """Return ``True`` if ``alias`` still appears as a bare name (non-import).

    Guards against dropping ``import old as alias`` when a residual value
    reference (e.g. ``x = alias``) would otherwise be left unbound.
    """
    counter = _BareNameUsageCounter(alias)
    tree.visit(counter)
    return counter.count > 0


def _iter_workspace_py_files(
    workspace_root: Path, exclude: Iterable[Path]
) -> list[Path]:
    """Return all ``.py`` files in ``workspace_root`` excluding given paths."""
    excluded = {p.resolve() for p in exclude}
    return sorted(
        p
        for p in workspace_root.rglob("*.py")
        if p.resolve() not in excluded
        and not any(part.startswith(".") for part in p.parts)
    )


def _discover_callers(
    workspace_root: Path,
    moved_names: Sequence[str],
    from_module: str,
    exclude: Iterable[Path] = (),
) -> list[Path]:
    """Return caller files that import any ``moved_names`` from ``from_module``.

    Scans ``.py`` files under ``workspace_root`` with a cheap textual
    pre-filter (``from <from_module> import``) to avoid parsing every file,
    then confirms the match by parsing the candidate with libcst and
    collecting ``ImportFrom`` targets via :class:`_CollectOldImport`. This
    handles multi-line ``from <from_module> import (\n  foo,\n)`` imports
    that a per-line textual scan would miss. Matches are validated again
    via libcst during rewriting.
    """
    needle = f"from {from_module} import"
    moved = set(moved_names)
    matches: list[Path] = []
    for path in _iter_workspace_py_files(workspace_root, exclude):
        try:
            text = path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        if needle not in text:
            continue
        try:
            tree = cst.parse_module(text)
        except cst.ParserSyntaxError:
            # Textual match but unparseable: keep it as a candidate so the
            # downstream rewrite/validation phase surfaces the parse error
            # (and rolls back) rather than silently dropping the caller.
            matches.append(path)
            continue
        collector = _CollectOldImport(from_module, moved)
        tree.visit(collector)
        if collector.matched_names:
            matches.append(path)
    return matches


def _discover_module_import_callers(
    workspace_root: Path,
    from_module: str,
    exclude: Iterable[Path] = (),
) -> list[Path]:
    """Return caller files that contain ``import from_module[ as X]``.

    Textual pre-filter: matches are validated via libcst during rewriting.
    """
    pattern = re.compile(
        rf"^\s*import\s+{re.escape(from_module)}(?:\s|,|$)",
        re.MULTILINE,
    )
    matches: list[Path] = []
    for path in _iter_workspace_py_files(workspace_root, exclude):
        try:
            text = path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        if pattern.search(text):
            matches.append(path)
    return matches
