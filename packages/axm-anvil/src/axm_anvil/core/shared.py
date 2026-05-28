"""Shared helper classification for the move pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field

import libcst as cst

from axm_anvil._cst.blocks import Block, _collect_refs

__all__ = ["SharedInfo", "_classify_shared_helpers"]


@dataclass
class SharedInfo:
    """Usage record for a copied helper.

    ``used_by_moved`` lists moved block names that transitively reference
    the helper; ``used_by_remaining`` lists remaining source symbols that
    do the same. A helper is "shared" iff both sets are non-empty.
    """

    used_by_moved: set[str] = field(default_factory=set)
    used_by_remaining: set[str] = field(default_factory=set)


def _assign_target(inner: cst.BaseSmallStatement) -> str | None:
    match inner:
        case cst.Assign(targets=[cst.AssignTarget(target=cst.Name(value=name))]):
            return name
        case cst.AnnAssign(target=cst.Name(value=name)):
            return name
    return None


def _stmt_target(stmt: cst.SimpleStatementLine) -> str | None:
    for inner in stmt.body:
        if (tgt := _assign_target(inner)) is not None:
            return tgt
    return None


def _top_level_refs(tree: cst.Module) -> dict[str, set[str]]:
    refs: dict[str, set[str]] = {}
    for stmt in tree.body:
        if isinstance(stmt, cst.ClassDef | cst.FunctionDef):
            name = stmt.name.value
            refs[name] = _collect_refs(stmt, name)
        elif isinstance(stmt, cst.SimpleStatementLine) and (tgt := _stmt_target(stmt)):
            refs[tgt] = _collect_refs(stmt, tgt)
    return refs


def _transitive_closure(start: set[str], graph: dict[str, set[str]]) -> set[str]:
    visited: set[str] = set()
    queue = list(start)
    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        for ref in graph.get(current, ()):
            if ref not in visited:
                queue.append(ref)
    return visited


def _classify_single_helper(
    helper: str,
    block_closures: dict[str, set[str]],
    remaining_closures: dict[str, set[str]],
) -> SharedInfo | None:
    used_by_moved = {
        block_name
        for block_name, closure in block_closures.items()
        if helper in closure
    }
    used_by_remaining = {
        sym for sym, closure in remaining_closures.items() if helper in closure
    }
    if used_by_moved and used_by_remaining:
        return SharedInfo(
            used_by_moved=used_by_moved,
            used_by_remaining=used_by_remaining,
        )
    return None


def _classify_shared_helpers(
    blocks: list[Block],
    needed_helpers: set[str],
    source_tree_after_remove: cst.Module,
) -> dict[str, SharedInfo]:
    """Return shared-helper classification for the current move plan.

    A helper is shared iff it is transitively referenced by at least one
    moved block AND by at least one remaining top-level symbol in
    ``source_tree_after_remove``.
    """
    source_refs = _top_level_refs(source_tree_after_remove)

    block_closures: dict[str, set[str]] = {
        block.name: _transitive_closure(set(block.referenced_names), source_refs)
        for block in blocks
    }

    remaining_closures: dict[str, set[str]] = {
        name: _transitive_closure(set(direct_refs), source_refs)
        for name, direct_refs in source_refs.items()
        if name not in needed_helpers
    }

    result: dict[str, SharedInfo] = {}
    for helper in needed_helpers:
        info = _classify_single_helper(helper, block_closures, remaining_closures)
        if info is not None:
            result[helper] = info
    return result
