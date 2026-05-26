"""Caller rewriting: redirect ``from old_module import Symbol`` to ``new_module``."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import libcst as cst
from libcst.codemod import CodemodContext
from libcst.codemod.visitors import AddImportsVisitor

from axm_anvil._cst.transformers import _AttributeRewriter

__all__ = [
    "CallerRewrite",
    "_discover_callers",
    "_discover_module_import_callers",
    "_module_path_from_file",
    "_rewrite_caller_text",
    "_rewrite_module_import_caller",
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


def _module_path_from_file(file_path: Path, workspace_root: Path) -> str:
    """Derive the dotted module path for ``file_path`` under ``workspace_root``.

    Strips a leading ``src/`` segment if present and drops the ``.py`` suffix.
    """
    rel = file_path.resolve().relative_to(workspace_root.resolve())
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


def _find_import_line(text: str, old_module: str) -> tuple[int, str] | None:
    """Return ``(lineno, line_text)`` of the first ``from old_module import`` line."""
    for idx, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith(f"from {old_module} import"):
            return idx, line
    return None


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


def _rewrite_caller_text(
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

    located = _find_import_line(text, old_module)
    line_no = located[0] if located else 1
    old_line = located[1].strip() if located else ""

    new_tree = tree.visit(_RewriteOldImport(old_module, moved))

    context = _add_new_imports(symbols, collector.matched_names, new_module)
    final_tree = AddImportsVisitor(context).transform_module(new_tree)

    new_stmt = _format_new_import_stmt(symbols, collector.matched_names, new_module)

    rewrite = CallerRewrite(file="", line=line_no, old=old_line, new=new_stmt)
    return final_tree.code, [rewrite]


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
    any_rewritten = False
    current_tree: cst.Module = tree
    for alias in collector.aliases:
        wrapper = cst.metadata.MetadataWrapper(current_tree)
        rewriter = _AttributeRewriter(
            old_module_alias=alias,
            new_module=new_module,
            symbols=moved,
        )
        rewritten = wrapper.visit(rewriter)
        if rewritten.code != current_tree.code:
            any_rewritten = True
        if rewriter.kept_usages == 0 and rewritten.code != current_tree.code:
            aliases_to_remove.add(alias)
        current_tree = rewritten

    if not any_rewritten:
        return text, []

    context = CodemodContext()
    AddImportsVisitor.add_needed_import(context, new_module)
    current_tree = AddImportsVisitor(context).transform_module(current_tree)

    if aliases_to_remove:
        current_tree = current_tree.visit(
            _RemoveModuleImports(old_module, aliases_to_remove)
        )

    rewrite = CallerRewrite(
        file="",
        line=1,
        old=f"import {old_module}",
        new=f"import {new_module}",
    )
    return current_tree.code, [rewrite]


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

    Scans ``.py`` files under ``workspace_root`` textually for the
    ``from <from_module> import`` line. Matches are later validated via
    libcst during rewriting.
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
        for line in text.splitlines():
            if not line.lstrip().startswith(needle):
                continue
            remainder = line.split("import", 1)[1]
            imported = {
                piece.strip().split()[0]
                for piece in remainder.split(",")
                if piece.strip()
            }
            if imported & moved:
                matches.append(path)
                break
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
