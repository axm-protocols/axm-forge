"""Source-module dependency gathering (imports + module-level constants)."""

from __future__ import annotations

from dataclasses import dataclass

import libcst as cst

from axm_anvil._cst import dotted_name
from axm_anvil._cst.visitors import ReferenceCollector

__all__ = [
    "ImportInfo",
    "_gather_target_existing",
    "_gather_target_imports",
    "gather_source_constants",
    "gather_source_helpers",
    "gather_source_imports",
    "topo_sort_constants",
]


@dataclass
class ImportInfo:
    module: str = ""
    obj: str | None = None
    alias: str | None = None
    relative: int = 0


def _alias_asname(alias_node: cst.ImportAlias) -> str | None:
    if alias_node.asname is not None and isinstance(alias_node.asname.name, cst.Name):
        return alias_node.asname.name.value
    return None


def _import_info_from_import_stmt(
    node: cst.Import, mapping: dict[str, ImportInfo]
) -> None:
    for alias_node in node.names:
        full = dotted_name(alias_node.name)
        if not full:
            continue
        asname = _alias_asname(alias_node)
        local = asname or full.split(".")[0]
        mapping[local] = ImportInfo(module=full, alias=asname)


def _import_info_from_importfrom_stmt(
    node: cst.ImportFrom, mapping: dict[str, ImportInfo]
) -> None:
    if isinstance(node.names, cst.ImportStar):
        return
    module = dotted_name(node.module) if node.module else ""
    relative = len(node.relative)
    for alias_node in node.names:
        if not isinstance(alias_node.name, cst.Name):
            continue
        obj = alias_node.name.value
        asname = _alias_asname(alias_node)
        local = asname or obj
        mapping[local] = ImportInfo(
            module=module,
            obj=obj,
            alias=asname,
            relative=relative,
        )


def gather_source_imports(tree: cst.Module) -> dict[str, ImportInfo]:
    """Map local names to the ``ImportInfo`` describing their origin."""
    mapping: dict[str, ImportInfo] = {}
    for stmt in tree.body:
        if not isinstance(stmt, cst.SimpleStatementLine):
            continue
        for inner in stmt.body:
            if isinstance(inner, cst.Import):
                _import_info_from_import_stmt(inner, mapping)
            elif isinstance(inner, cst.ImportFrom):
                _import_info_from_importfrom_stmt(inner, mapping)
    return mapping


def _gather_target_imports(tree: cst.Module) -> dict[str, ImportInfo]:
    """Map local names already imported in the target tree to their ``ImportInfo``.

    Mirrors :func:`gather_source_imports` but is used to detect names that
    are already in scope in the target file before adding new imports.
    """
    mapping: dict[str, ImportInfo] = {}
    for stmt in tree.body:
        if not isinstance(stmt, cst.SimpleStatementLine):
            continue
        for inner in stmt.body:
            if isinstance(inner, cst.Import):
                _import_info_from_import_stmt(inner, mapping)
            elif isinstance(inner, cst.ImportFrom):
                _import_info_from_importfrom_stmt(inner, mapping)
    return mapping


def gather_source_constants(
    tree: cst.Module,
) -> dict[str, cst.SimpleStatementLine]:
    """Map module-level constant names to their ``SimpleStatementLine``."""
    mapping: dict[str, cst.SimpleStatementLine] = {}
    for stmt in tree.body:
        if not isinstance(stmt, cst.SimpleStatementLine):
            continue
        for inner in stmt.body:
            if isinstance(inner, cst.Assign):
                if len(inner.targets) == 1 and isinstance(
                    inner.targets[0].target, cst.Name
                ):
                    mapping[inner.targets[0].target.value] = stmt
            elif isinstance(inner, cst.AnnAssign) and isinstance(
                inner.target, cst.Name
            ):
                mapping[inner.target.value] = stmt
    return mapping


def gather_source_helpers(
    tree: cst.Module,
) -> dict[str, cst.FunctionDef | cst.ClassDef]:
    """Map top-level ``FunctionDef`` / ``ClassDef`` names to their node."""
    mapping: dict[str, cst.FunctionDef | cst.ClassDef] = {}
    for stmt in tree.body:
        if isinstance(stmt, cst.FunctionDef | cst.ClassDef):
            mapping[stmt.name.value] = stmt
    return mapping


def topo_sort_constants(
    constants: dict[str, cst.SimpleStatementLine],
) -> list[cst.SimpleStatementLine]:
    """Topologically sort constants so deps appear before dependents.

    Cycles are tolerated — back-edges are skipped and all members are
    still emitted (Python would raise ``NameError`` at runtime for a
    genuine cycle, so arbitrary order among cycle members is acceptable).
    """
    keys = set(constants)
    deps: dict[str, set[str]] = {}
    for name, stmt in constants.items():
        collector = ReferenceCollector()
        stmt.visit(collector)
        deps[name] = (collector.names & keys) - {name}

    ordered: list[str] = []
    visited: set[str] = set()
    in_stack: set[str] = set()

    def visit(node: str) -> None:
        """DFS post-order helper that emits constants in dependency order."""
        if node in visited or node in in_stack:
            return
        in_stack.add(node)
        for dep in deps[node]:
            visit(dep)
        in_stack.discard(node)
        visited.add(node)
        ordered.append(node)

    for name in constants:
        visit(name)

    return [constants[n] for n in ordered]


def _names_from_assign(node: cst.Assign) -> set[str]:
    return {t.target.value for t in node.targets if isinstance(t.target, cst.Name)}


def _names_from_ann_assign(node: cst.AnnAssign) -> set[str]:
    if isinstance(node.target, cst.Name):
        return {node.target.value}
    return set()


def _names_from_simple_stmt(stmt: cst.SimpleStatementLine) -> set[str]:
    names: set[str] = set()
    for inner in stmt.body:
        if isinstance(inner, cst.Assign):
            names |= _names_from_assign(inner)
        elif isinstance(inner, cst.AnnAssign):
            names |= _names_from_ann_assign(inner)
    return names


def _gather_target_existing(tree: cst.Module) -> set[str]:
    """Return the set of top-level names already defined in ``tree``."""
    names: set[str] = set()
    for stmt in tree.body:
        match stmt:
            case cst.ClassDef() | cst.FunctionDef():
                names.add(stmt.name.value)
            case cst.SimpleStatementLine():
                names |= _names_from_simple_stmt(stmt)
    return names
