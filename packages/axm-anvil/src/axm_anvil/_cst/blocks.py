"""Top-level symbol block extraction from a libcst Module."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import libcst as cst

from axm_anvil._cst.visitors import ReferenceCollector

__all__ = ["Block", "extract_blocks"]


@dataclass
class Block:
    """A top-level symbol definition extracted from a module.

    Carries the CST statement that defines the symbol, the leading
    formatting lines that immediately precede it (used to preserve
    ``# --- Section ---`` comments), and the set of external names
    referenced by its body.
    """

    name: str
    node: cst.BaseStatement
    leading_lines: list[cst.EmptyLine] = field(default_factory=list)
    referenced_names: set[str] = field(default_factory=set)


def _collect_refs(node: cst.CSTNode, exclude: str) -> set[str]:
    collector = ReferenceCollector()
    node.visit(collector)
    return collector.names - {exclude}


def _make_block(
    name: str, stmt: cst.BaseStatement, leading: list[cst.EmptyLine]
) -> Block:
    return Block(
        name=name,
        node=stmt,
        leading_lines=leading,
        referenced_names=_collect_refs(stmt, name),
    )


def _assigned_name_in(stmt: cst.SimpleStatementLine, wanted: set[str]) -> str | None:
    for inner in stmt.body:
        assign_name = _assignment_target(inner)
        if assign_name and assign_name in wanted:
            return assign_name
    return None


def extract_blocks(tree: cst.Module, symbol_names: Sequence[str]) -> list[Block]:
    """Extract ``Block`` records for each requested top-level symbol.

    Supports ``ClassDef``, ``FunctionDef``, ``Assign``, and ``AnnAssign``
    at module scope. Missing symbols are silently omitted.
    """
    wanted = set(symbol_names)
    blocks: list[Block] = []
    for index, stmt in enumerate(tree.body):
        leading = _leading_lines_for(tree, stmt, index)
        if isinstance(stmt, cst.ClassDef | cst.FunctionDef):
            if stmt.name.value in wanted:
                blocks.append(_make_block(stmt.name.value, stmt, leading))
            continue
        if isinstance(stmt, cst.SimpleStatementLine):
            assign_name = _assigned_name_in(stmt, wanted)
            if assign_name is not None:
                blocks.append(_make_block(assign_name, stmt, leading))
    return blocks


def _leading_lines_for(
    tree: cst.Module, stmt: cst.BaseStatement, index: int
) -> list[cst.EmptyLine]:
    own: list[cst.EmptyLine] = list(getattr(stmt, "leading_lines", []))
    if index == 0:
        return list(tree.header) + own
    return own


def _assignment_target(node: cst.CSTNode) -> str | None:
    if isinstance(node, cst.Assign):
        if len(node.targets) == 1:
            target = node.targets[0].target
            if isinstance(target, cst.Name):
                return target.value
        return None
    if isinstance(node, cst.AnnAssign) and isinstance(node.target, cst.Name):
        return node.target.value
    return None
