"""Atomic move pipeline: relocate top-level symbols between modules."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import libcst as cst
from libcst.codemod import CodemodContext
from libcst.codemod.visitors import AddImportsVisitor

from axm_anvil._cst.blocks import _collect_refs, _extract_blocks
from axm_anvil._cst.overloads import _detect_overload_group
from axm_anvil._cst.transformers import _RemoveSymbols
from axm_anvil.core.callers import (
    CallerRewrite,
    _discover_callers,
    _discover_module_import_callers,
    _module_path_from_file,
    _rewrite_caller_text,
    _rewrite_module_import_caller,
)
from axm_anvil.core.cycles import GraphEdits, detect_new_cycle
from axm_anvil.core.deps import (
    ImportInfo,
    _gather_source_constants,
    _gather_source_helpers,
    _gather_source_imports,
    _gather_target_existing,
    _gather_target_imports,
    _topo_sort_constants,
)
from axm_anvil.core.plan import (
    ImportCycleError,
    MovePlan,
    MoveValidationError,
    OverloadPartialMoveError,
    SharedHelperDetection,
    SharedHelpersError,
    SymbolAlreadyExistsError,
    SymbolNotFoundError,
)
from axm_anvil.core.postprocess import _ruff_fix
from axm_anvil.core.shared import _classify_shared_helpers

__all__ = [
    "ImportCycleError",
    "MoveValidationError",
    "OverloadPartialMoveError",
    "SymbolAlreadyExistsError",
    "SymbolNotFoundError",
    "batch_edit",
    "move_symbols",
]


def batch_edit(path: str | Path, operations: list[dict[str, Any]]) -> None:
    """Apply a batch of file operations atomically via ``axm-edit``.

    Accepts dict-shaped operations (``{op, file, edits|content}``) and
    delegates to :func:`axm_edit.core.engine.batch_apply`. Raises on any
    validation error so callers can trigger rollback.
    """
    from axm_edit.core.engine import batch_apply
    from axm_edit.models.operations import CreateOp, DeleteOp, Edit, ReplaceOp

    ops: list[Any] = []
    for op in operations:
        kind = op.get("op")
        if kind == "replace":
            edits = op["edits"]
            if len(edits) == 1 and edits[0].get("old", "") == "":
                ops.append(
                    CreateOp(
                        file=op["file"],
                        content=edits[0]["new"],
                        overwrite=True,
                    )
                )
            else:
                ops.append(
                    ReplaceOp(
                        file=op["file"],
                        edits=[Edit(**e) for e in edits],
                    )
                )
        elif kind == "create":
            ops.append(
                CreateOp(
                    file=op["file"],
                    content=op["content"],
                    overwrite=bool(op.get("overwrite", False)),
                )
            )
        elif kind == "delete":
            ops.append(DeleteOp(file=op["file"]))
        else:
            raise ValueError(f"Unknown op kind: {kind!r}")
    result = batch_apply(Path(path), ops)
    if not result.success:
        raise RuntimeError(f"batch_edit failed: {result.error}")


def _find_workspace_root(start: Path) -> Path:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return current


def _parse_symbol_spec(spec: str) -> tuple[str, int | None]:
    if ":" in spec:
        name, idx = spec.split(":", 1)
        try:
            return name, int(idx)
        except ValueError:
            return spec, None
    return spec, None


def _expand_overloads(
    source_tree: cst.Module, raw_names: Sequence[str]
) -> tuple[list[str], list[str]]:
    """Expand overload groups, detect partial-move requests.

    Returns ``(expanded_unique_names, moved_names_for_plan)``.
    Raises ``OverloadPartialMoveError`` if any symbol is a partial
    overload reference.
    """
    expanded: list[str] = []
    seen: set[str] = set()
    user_reported: list[str] = []
    for raw in raw_names:
        name, idx = _parse_symbol_spec(raw)
        group = _detect_overload_group(source_tree, name)
        if idx is not None:
            if group:
                raise OverloadPartialMoveError(
                    f"{name!r} is part of an overload group of {len(group)} "
                    "signatures; move the full group by name without ':idx'"
                )
            if name not in seen:
                expanded.append(name)
                seen.add(name)
                user_reported.append(name)
            continue
        if group:
            if name not in seen:
                expanded.append(name)
                seen.add(name)
                user_reported.append(name)
            continue
        if name not in seen:
            expanded.append(name)
            seen.add(name)
            user_reported.append(name)
    return expanded, user_reported


def _assign_target_names(assign: cst.Assign) -> set[str]:
    return {
        tgt.target.value for tgt in assign.targets if isinstance(tgt.target, cst.Name)
    }


def _ann_assign_name(ann: cst.AnnAssign) -> str | None:
    return ann.target.value if isinstance(ann.target, cst.Name) else None


def _simple_stmt_names(stmt: cst.SimpleStatementLine) -> set[str]:
    names: set[str] = set()
    for inner in stmt.body:
        if isinstance(inner, cst.Assign):
            names.update(_assign_target_names(inner))
        elif isinstance(inner, cst.AnnAssign):
            name = _ann_assign_name(inner)
            if name is not None:
                names.add(name)
    return names


def _source_symbol_names(tree: cst.Module) -> set[str]:
    """Return top-level symbol names (classes, functions, assignments) in a module."""
    names: set[str] = set()
    for stmt in tree.body:
        if isinstance(stmt, cst.ClassDef | cst.FunctionDef):
            names.add(stmt.name.value)
        elif isinstance(stmt, cst.SimpleStatementLine):
            names.update(_simple_stmt_names(stmt))
    return names


def _expand_refs_one_level(
    refs: Iterable[str],
    seen: set[str],
    queue: list[str],
) -> None:
    """Append unseen refs to `queue`, marking them in `seen` in place."""
    for ref in refs:
        if ref not in seen:
            seen.add(ref)
            queue.append(ref)


@dataclass
class _BfsState:
    """Mutable BFS traversal state for transitive dependency collection."""

    source_helpers: dict[str, cst.FunctionDef | cst.ClassDef]
    source_constants: dict[str, cst.SimpleStatementLine]
    collected_helpers: dict[str, cst.FunctionDef | cst.ClassDef] = field(
        default_factory=dict,
    )
    collected_constants: dict[str, cst.SimpleStatementLine] = field(
        default_factory=dict,
    )
    seen: set[str] = field(default_factory=set)
    queue: list[str] = field(default_factory=list)


def _visit_dep_name(
    name: str,
    block_names: set[str],
    state: _BfsState,
) -> None:
    """Resolve one BFS name: record it as helper/constant and expand its refs."""
    if name in block_names:
        return
    node: cst.FunctionDef | cst.ClassDef | cst.SimpleStatementLine | None = None
    if name in state.source_helpers:
        node = state.source_helpers[name]
        state.collected_helpers[name] = node
    elif name in state.source_constants:
        node = state.source_constants[name]
        state.collected_constants[name] = node
    if node is not None:
        _expand_refs_one_level(_collect_refs(node, name), state.seen, state.queue)


def _collect_transitive_deps(
    blocks: list[Any],
    source_helpers: dict[str, cst.FunctionDef | cst.ClassDef],
    source_constants: dict[str, cst.SimpleStatementLine],
) -> tuple[
    dict[str, cst.FunctionDef | cst.ClassDef],
    dict[str, cst.SimpleStatementLine],
]:
    """BFS transitive closure over helpers and constants from block refs.

    Returns collected helpers and constants in BFS-discovery order
    (dict insertion order). Stable on reference cycles.
    """
    block_names = {b.name for b in blocks}
    state = _BfsState(
        source_helpers=source_helpers,
        source_constants=source_constants,
    )
    for block in blocks:
        _expand_refs_one_level(block.referenced_names, state.seen, state.queue)
    while state.queue:
        _visit_dep_name(state.queue.pop(0), block_names, state)
    return state.collected_helpers, state.collected_constants


def _extract_assign_target_name(stmt: cst.SimpleStatementLine) -> str | None:
    """Return the top-level name bound by a simple assignment, if any."""
    for inner in stmt.body:
        if isinstance(inner, cst.Assign):
            if len(inner.targets) == 1 and isinstance(
                inner.targets[0].target, cst.Name
            ):
                return inner.targets[0].target.value
        elif isinstance(inner, cst.AnnAssign) and isinstance(inner.target, cst.Name):
            return inner.target.value
    return None


def _collect_top_level_refs(
    module: cst.Module,
) -> tuple[set[str], dict[str, set[str]]]:
    """Collect top-level names and their outgoing reference sets."""
    all_top_names: set[str] = set()
    refs_of: dict[str, set[str]] = {}
    for stmt in module.body:
        if isinstance(stmt, cst.ClassDef | cst.FunctionDef):
            name = stmt.name.value
            all_top_names.add(name)
            refs_of[name] = _collect_refs(stmt, name)
        elif isinstance(stmt, cst.SimpleStatementLine):
            tgt_name = _extract_assign_target_name(stmt)
            if tgt_name:
                all_top_names.add(tgt_name)
                refs_of[tgt_name] = _collect_refs(stmt, tgt_name)
    return all_top_names, refs_of


def _filter_still_referenced(
    candidates: set[str],
    staying: set[str],
    refs_of: dict[str, set[str]],
) -> set[str]:
    """Iterate to stability, promoting candidates referenced by staying names."""
    changed = True
    while changed:
        changed = False
        for cand in list(candidates):
            if any(cand in refs_of.get(s, set()) for s in staying):
                staying.add(cand)
                candidates.discard(cand)
                changed = True
    return candidates


def _compute_source_orphans(
    source_tree_after_blocks: cst.Module,
    copied_helpers: set[str],
    copied_constants: set[str],
) -> set[str]:
    """Return copied helpers/constants that no remaining symbol references.

    Iterates to stability: a candidate is only marked removable if nothing
    that is staying (including other candidates that turned out to be
    still-needed) references it.
    """
    candidates = copied_helpers | copied_constants
    all_top_names, refs_of = _collect_top_level_refs(source_tree_after_blocks)
    candidates &= all_top_names
    staying = all_top_names - candidates
    return _filter_still_referenced(candidates, staying, refs_of)


def _collect_external_refs(
    blocks: list[Any],
    collected_helpers: dict[str, cst.FunctionDef | cst.ClassDef],
    collected_constants: dict[str, cst.SimpleStatementLine],
) -> set[str]:
    all_referenced: set[str] = set()
    for block in blocks:
        all_referenced |= block.referenced_names
    for h_name, h_node in collected_helpers.items():
        all_referenced |= _collect_refs(h_node, h_name)
    for c_name, c_stmt in collected_constants.items():
        all_referenced |= _collect_refs(c_stmt, c_name)
    locally_defined = (
        set(collected_helpers) | set(collected_constants) | {b.name for b in blocks}
    )
    return all_referenced - locally_defined


def _register_import(
    context: CodemodContext,
    info: Any,
    imports_added: list[str],
) -> None:
    if info.obj is not None:
        module = info.module if not info.relative else None
        if module is None:
            return
        AddImportsVisitor.add_needed_import(
            context, module, info.obj, asname=info.alias
        )
        label = f"from {module} import {info.obj}"
    else:
        AddImportsVisitor.add_needed_import(context, info.module, asname=info.alias)
        label = f"import {info.module}"
        if info.alias:
            label += f" as {info.alias}"
    if label not in imports_added:
        imports_added.append(label)


def _import_modules_match(source_info: Any, target_info: Any) -> bool:
    """Return True iff source/target imports refer to the same module.

    Conservatively treats relative imports on either side as non-matching
    unless both have identical relative depth and module string.
    """
    if source_info.relative or target_info.relative:
        return (
            source_info.relative == target_info.relative
            and source_info.module == target_info.module
        )
    return source_info.module == target_info.module


def _apply_imports(
    target_tree: cst.Module,
    external_refs: set[str],
    source_imports: dict[str, Any],
    target_imports: dict[str, Any],
) -> tuple[cst.Module, list[str], list[str]]:
    context = CodemodContext()
    imports_added: list[str] = []
    redundant_warnings: list[str] = []
    for name in sorted(external_refs):
        info = source_imports.get(name)
        if info is None:
            continue
        existing = target_imports.get(name)
        if existing is not None:
            if not _import_modules_match(info, existing):
                redundant_warnings.append(
                    f"redundant import: {name} already imported from "
                    f"{existing.module}; source had {info.module}"
                )
            continue
        _register_import(context, info, imports_added)
    return (
        AddImportsVisitor(context).transform_module(target_tree),
        imports_added,
        redundant_warnings,
    )


def _build_constants_body(
    collected_constants: dict[str, cst.SimpleStatementLine],
    target_existing: set[str],
) -> tuple[list[cst.BaseStatement], list[str]]:
    body: list[cst.BaseStatement] = []
    constants_added: list[str] = []
    for stmt in _topo_sort_constants(collected_constants):
        const_name = _constant_name(stmt)
        if not const_name or const_name in target_existing:
            continue
        body.append(stmt)
        constants_added.append(const_name)
    return body, constants_added


def _build_helpers_body(
    source_helpers_order: list[str],
    collected_helpers: dict[str, cst.FunctionDef | cst.ClassDef],
    target_existing: set[str],
) -> list[cst.BaseStatement]:
    body: list[cst.BaseStatement] = []
    for h_name in source_helpers_order:
        if h_name not in collected_helpers or h_name in target_existing:
            continue
        node = collected_helpers[h_name]
        if hasattr(node, "with_changes"):
            node = node.with_changes(leading_lines=[cst.EmptyLine(), cst.EmptyLine()])
        body.append(node)
    return body


def _build_blocks_body(blocks: list[Any]) -> list[cst.BaseStatement]:
    body: list[cst.BaseStatement] = []
    for block in blocks:
        new_node = block.node
        if hasattr(new_node, "with_changes"):
            new_node = new_node.with_changes(
                leading_lines=[cst.EmptyLine(), cst.EmptyLine()]
            )
        body.append(new_node)
    return body


def _build_target_tree(  # noqa: PLR0913
    target_tree: cst.Module,
    blocks: list[Any],
    source_imports: dict[str, Any],
    collected_constants: dict[str, cst.SimpleStatementLine],
    collected_helpers: dict[str, cst.FunctionDef | cst.ClassDef],
    source_helpers_order: list[str],
) -> tuple[cst.Module, list[str], list[str], list[str]]:
    """Assemble the target module: imports + constants + helpers + blocks.

    Returns ``(new_tree, imports_added_labels, constants_added_names,
    redundant_import_warnings)``.
    """
    target_existing = _gather_target_existing(target_tree)
    target_imports = _gather_target_imports(target_tree)
    external_refs = _collect_external_refs(
        blocks, collected_helpers, collected_constants
    )
    tree_with_imports, imports_added, redundant_warnings = _apply_imports(
        target_tree, external_refs, source_imports, target_imports
    )
    constants_body, constants_added = _build_constants_body(
        collected_constants, target_existing
    )
    helpers_body = _build_helpers_body(
        source_helpers_order, collected_helpers, target_existing
    )
    blocks_body = _build_blocks_body(blocks)
    new_body = (
        list(tree_with_imports.body) + constants_body + helpers_body + blocks_body
    )
    return (
        tree_with_imports.with_changes(body=new_body),
        imports_added,
        constants_added,
        redundant_warnings,
    )


def _constant_name(stmt: cst.SimpleStatementLine) -> str | None:
    for inner in stmt.body:
        if isinstance(inner, cst.Assign):
            if len(inner.targets) == 1 and isinstance(
                inner.targets[0].target, cst.Name
            ):
                return inner.targets[0].target.value
        elif isinstance(inner, cst.AnnAssign) and isinstance(inner.target, cst.Name):
            return inner.target.value
    return None


def _validate_and_expand(
    source_tree: cst.Module,
    target_tree: cst.Module,
    symbol_names: Sequence[str],
) -> tuple[list[str], list[str]]:
    """Expand overload aliases and validate presence in source / absence in target."""
    expanded_names, moved_names = _expand_overloads(source_tree, symbol_names)

    source_names = _source_symbol_names(source_tree)
    for name in expanded_names:
        if name not in source_names:
            raise SymbolNotFoundError(name)

    target_existing = _gather_target_existing(target_tree)
    for name in expanded_names:
        if name in target_existing:
            raise SymbolAlreadyExistsError(name)

    return expanded_names, moved_names


def _extract_moved_blocks(
    source_tree: cst.Module, expanded_names: Sequence[str]
) -> tuple[set[str], list[Any]]:
    """Extract blocks (with overload groups expanded) and symbols to remove."""
    remove_targets: set[str] = set()
    blocks: list[Any] = []
    for name in expanded_names:
        group = _detect_overload_group(source_tree, name)
        if group:
            for func in group:
                remove_targets.add(func.name.value)
            for func in group:
                blocks.append(
                    type(
                        "Block",
                        (),
                        {
                            "name": func.name.value,
                            "node": func,
                            "leading_lines": [],
                            "referenced_names": _collect_refs(func, func.name.value),
                        },
                    )()
                )
        else:
            remove_targets.add(name)
            extracted = _extract_blocks(source_tree, [name])
            blocks.extend(extracted)
    return remove_targets, blocks


def _build_trees(
    source_tree: cst.Module,
    target_tree: cst.Module,
    blocks: list[Any],
    remove_targets: set[str],
    shared_helpers: str,
) -> tuple[cst.Module, cst.Module, list[str], list[str], dict[str, Any], list[str]]:
    """Build new source/target trees and return added imports/constants + shared map."""
    source_imports = _gather_source_imports(source_tree)
    source_constants = _gather_source_constants(source_tree)
    source_helpers = _gather_source_helpers(source_tree)

    collected_helpers, collected_constants = _collect_transitive_deps(
        blocks, source_helpers, source_constants
    )
    for moved in remove_targets:
        collected_helpers.pop(moved, None)
        collected_constants.pop(moved, None)

    (
        new_target_tree,
        imports_added,
        constants_added,
        redundant_import_warnings,
    ) = _build_target_tree(
        target_tree,
        blocks,
        source_imports,
        collected_constants,
        collected_helpers,
        list(source_helpers.keys()),
    )

    new_source_tree = source_tree.visit(_RemoveSymbols(remove_targets))

    shared_map = _classify_shared_helpers(
        blocks, set(collected_helpers.keys()), new_source_tree
    )
    if shared_map and shared_helpers == "error":
        raise SharedHelpersError(sorted(shared_map.keys()))

    orphans = _compute_source_orphans(
        new_source_tree,
        set(collected_helpers.keys()),
        set(collected_constants.keys()),
    )
    orphans -= set(shared_map.keys())
    if orphans:
        new_source_tree = new_source_tree.visit(_RemoveSymbols(orphans))

    return (
        new_source_tree,
        new_target_tree,
        imports_added,
        constants_added,
        shared_map,
        redundant_import_warnings,
    )


def _render_and_validate(
    new_source_tree: cst.Module, new_target_tree: cst.Module
) -> tuple[str, str]:
    """Render trees to text and validate parseability."""
    source_text_new = new_source_tree.code
    target_text_new = new_target_tree.code

    for rendered in (source_text_new, target_text_new):
        try:
            cst.parse_module(rendered)
        except Exception as exc:
            raise MoveValidationError(rendered, exc) from exc

    return source_text_new, target_text_new


def _build_plan(  # noqa: PLR0913
    source_text_new: str,
    target_text_new: str,
    moved_names: list[str],
    imports_added: list[str],
    constants_added: list[str],
    shared_map: dict[str, Any],
    callers_updated: list[CallerRewrite] | None = None,
    redundant_import_warnings: list[str] | None = None,
) -> MovePlan:
    """Assemble the MovePlan with shared-helper detections and warnings."""
    shared_detected = [
        SharedHelperDetection(
            name=name,
            used_by_moved=sorted(info.used_by_moved),
            used_by_remaining=sorted(info.used_by_remaining),
        )
        for name, info in sorted(shared_map.items())
    ]
    shared_warnings = [
        (
            f"Helper '{det.name}' is also used by "
            f"{', '.join(det.used_by_remaining)} (not moved) "
            "\u2014 duplicated in target"
        )
        for det in shared_detected
    ]
    warnings: list[str] = list(redundant_import_warnings or []) + list(shared_warnings)
    return MovePlan(
        source_text_new=source_text_new,
        target_text_new=target_text_new,
        moved_names=moved_names,
        imports_added=imports_added,
        constants_added=constants_added,
        warnings=warnings,
        shared_helpers_detected=shared_detected,
        callers_updated=list(callers_updated or []),
    )


def _process_callers(
    workspace_root: Path,
    moved_names: Sequence[str],
    source_path: Path,
    target_path: Path,
) -> tuple[dict[Path, tuple[str, str]], list[CallerRewrite]]:
    """Discover callers, rewrite their imports, and validate the results.

    Returns ``(caller_texts, rewrites)`` where ``caller_texts`` maps each
    caller path to ``(original_text, new_text)``. Raises
    :class:`MoveValidationError` if any caller fails to parse before or after
    rewrite. Files are only read — writes happen later via ``_apply_write``.
    """
    try:
        from_module = _module_path_from_file(source_path, workspace_root)
        new_module = _module_path_from_file(target_path, workspace_root)
    except ValueError:
        return {}, []

    from_callers = _discover_callers(
        workspace_root,
        moved_names,
        from_module,
        exclude=[source_path, target_path],
    )
    module_callers = _discover_module_import_callers(
        workspace_root,
        from_module,
        exclude=[source_path, target_path],
    )
    ordered_callers = _dedup_caller_paths(from_callers, module_callers)

    new_texts: dict[Path, tuple[str, str]] = {}
    rewrites: list[CallerRewrite] = []
    for caller_path in ordered_callers:
        try:
            original = caller_path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        result = _rewrite_one_caller(original, from_module, new_module, moved_names)
        if result is None:
            continue
        current_text, caller_rewrites = result
        file_str = _caller_relpath(caller_path, workspace_root)
        for rewrite in caller_rewrites:
            rewrite.file = file_str
            rewrites.append(rewrite)
        new_texts[caller_path] = (original, current_text)
    return new_texts, rewrites


def _dedup_caller_paths(
    from_callers: Sequence[Path], module_callers: Sequence[Path]
) -> list[Path]:
    """Return callers in stable order with duplicates (by resolved path) removed."""
    seen_paths: set[Path] = set()
    ordered: list[Path] = []
    for caller_path in list(from_callers) + list(module_callers):
        resolved = caller_path.resolve()
        if resolved in seen_paths:
            continue
        seen_paths.add(resolved)
        ordered.append(caller_path)
    return ordered


def _rewrite_one_caller(
    original: str,
    from_module: str,
    new_module: str,
    moved_names: Sequence[str],
) -> tuple[str, list[CallerRewrite]] | None:
    """Apply both rewrites and validate the result. Returns ``None`` if unchanged."""
    try:
        current_text, from_rewrites = _rewrite_caller_text(
            original, from_module, new_module, moved_names
        )
        current_text, attr_rewrites = _rewrite_module_import_caller(
            current_text, from_module, new_module, moved_names
        )
    except Exception as exc:
        raise MoveValidationError(original, exc) from exc
    caller_rewrites = list(from_rewrites) + list(attr_rewrites)
    if not caller_rewrites or current_text == original:
        return None
    try:
        cst.parse_module(current_text)
    except Exception as exc:
        raise MoveValidationError(current_text, exc) from exc
    return current_text, caller_rewrites


def _caller_relpath(caller_path: Path, workspace_root: Path) -> str:
    try:
        return str(caller_path.resolve().relative_to(workspace_root.resolve()))
    except ValueError:
        return str(caller_path)


def _apply_write(  # noqa: PLR0913
    source_path: Path,
    target_path: Path,
    source_text: str,
    target_text: str,
    source_text_new: str,
    target_text_new: str,
    workspace_root: Path | None,
    caller_texts: dict[Path, tuple[str, str]] | None = None,
) -> None:
    """Resolve workspace root and atomically write the new source/target texts."""
    root = (
        Path(workspace_root)
        if workspace_root is not None
        else _find_workspace_root(source_path)
    )
    try:
        source_rel = source_path.resolve().relative_to(root.resolve())
        target_rel = target_path.resolve().relative_to(root.resolve())
    except ValueError:
        root = source_path.resolve().parent
        source_rel = source_path.resolve().relative_to(root)
        target_rel = target_path.resolve().relative_to(root)

    operations: list[dict[str, Any]] = [
        {
            "op": "replace",
            "file": str(source_rel),
            "edits": [{"old": source_text, "new": source_text_new}],
        },
        {
            "op": "replace",
            "file": str(target_rel),
            "edits": [{"old": target_text, "new": target_text_new}],
        },
    ]
    if caller_texts:
        for caller_path, (old_text, new_text) in caller_texts.items():
            try:
                caller_rel = caller_path.resolve().relative_to(root.resolve())
            except ValueError:
                caller_rel = caller_path
            operations.append(
                {
                    "op": "replace",
                    "file": str(caller_rel),
                    "edits": [{"old": old_text, "new": new_text}],
                }
            )
    batch_edit(str(root), operations)


def _find_pkg_root(source_path: Path, workspace_root: Path) -> Path | None:
    """Return the topmost package directory (containing ``__init__.py``) that
    is still an ancestor of ``source_path`` and lies under ``workspace_root``.
    """
    current = source_path.resolve().parent
    root_resolved = workspace_root.resolve()
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


def _dotted_name_of(expr: cst.BaseExpression) -> str | None:
    """Return dotted-path string for a ``Name``/``Attribute`` expr, else ``None``."""
    if isinstance(expr, cst.Name):
        return expr.value
    if isinstance(expr, cst.Attribute):
        base = _dotted_name_of(expr.value)
        if base is None:
            return None
        return f"{base}.{expr.attr.value}"
    return None


def _extract_absolute_imports(tree: cst.Module, internal_modules: set[str]) -> set[str]:
    """Return the set of internal absolute module names imported by ``tree``."""
    out: set[str] = set()
    for stmt in tree.body:
        if not isinstance(stmt, cst.SimpleStatementLine):
            continue
        for inner in stmt.body:
            if isinstance(inner, cst.ImportFrom):
                _collect_from_import(inner, internal_modules, out)
            elif isinstance(inner, cst.Import):
                _collect_plain_import(inner, internal_modules, out)
    return out


def _collect_from_import(
    node: cst.ImportFrom, internal_modules: set[str], out: set[str]
) -> None:
    """Add to ``out`` the internal module referenced by ``from X import ...``."""
    if node.relative or node.module is None:
        return
    name = _dotted_name_of(node.module)
    if name is None:
        return
    resolved = _resolve_internal_module(name, internal_modules)
    if resolved is not None:
        out.add(resolved)


def _collect_plain_import(
    node: cst.Import, internal_modules: set[str], out: set[str]
) -> None:
    """Add to ``out`` the internal modules referenced by ``import X, Y``."""
    for alias in node.names:
        name = _dotted_name_of(alias.name)
        if name is not None and name in internal_modules:
            out.add(name)


def _pkg_module_name(py: Path, pkg_root: Path) -> str:
    rel = py.relative_to(pkg_root)
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    pkg_prefix = pkg_root.name
    return pkg_prefix + (("." + ".".join(parts)) if parts else "")


def _build_current_graph(
    pkg_root: Path,
) -> tuple[dict[str, set[str]], set[str]]:
    """Parse all ``.py`` files under ``pkg_root`` and build an import graph.

    Returns ``(graph, internal_modules)`` using fully-qualified dotted names.
    Parse failures on individual files are ignored so graph construction is
    best-effort; cycle detection only flags *new* cycles vs the current state.
    """
    path_to_mod: dict[Path, str] = {}
    modules: set[str] = set()
    for py in pkg_root.rglob("*.py"):
        if not py.is_file():
            continue
        mod_name = _pkg_module_name(py, pkg_root)
        modules.add(mod_name)
        path_to_mod[py] = mod_name

    graph: dict[str, set[str]] = {m: set() for m in modules}
    for py, mod_name in path_to_mod.items():
        try:
            tree = cst.parse_module(py.read_text())
        except Exception:  # noqa: BLE001, S112
            continue
        graph[mod_name] |= _extract_absolute_imports(tree, modules)
    return graph, modules


def _resolve_internal_module(module: str, internal_modules: set[str]) -> str | None:
    """Resolve ``module`` (or a dotted prefix) to an internal module name."""
    if module in internal_modules:
        return module
    parent = module
    while "." in parent:
        parent = parent.rsplit(".", 1)[0]
        if parent in internal_modules:
            return parent
    return None


def _block_implied_target_imports(  # noqa: PLR0913
    blocks: list[Any],
    source_tree: cst.Module,
    new_source_tree: cst.Module,
    source_module: str,
    target_module: str,
    internal_modules: set[str],
) -> set[str]:
    """Internal modules the target *should* import to support moved blocks.

    For each name referenced by a moved block, resolve it to the module that
    will own it after the move: a source-side import (carried over to the
    target) or a top-level symbol that stays in source.
    """
    source_imports = _gather_source_imports(source_tree)
    block_local_names = {b.name for b in blocks}
    remaining_source_names = _source_symbol_names(source_tree) - block_local_names
    _ = new_source_tree
    refs: set[str] = set()
    for block in blocks:
        refs |= block.referenced_names
    refs -= block_local_names

    out: set[str] = set()
    for ref in refs:
        resolved = _resolve_import_ref(
            ref, source_imports, internal_modules, target_module
        ) or _resolve_symbol_ref(
            ref, remaining_source_names, source_module, target_module
        )
        if resolved is not None:
            out.add(resolved)
    return out


def _resolve_import_ref(
    ref: str,
    source_imports: dict[str, ImportInfo],
    internal_modules: set[str],
    target_module: str,
) -> str | None:
    """Resolve ``ref`` via a source-side import to its internal owner module."""
    info = source_imports.get(ref)
    if info is None or info.relative or not info.module:
        return None
    resolved = _resolve_internal_module(info.module, internal_modules)
    if resolved is None or resolved == target_module:
        return None
    return resolved


def _resolve_symbol_ref(
    ref: str,
    remaining_source_names: set[str],
    source_module: str,
    target_module: str,
) -> str | None:
    """Resolve ``ref`` to ``source_module`` if it remains a top-level source symbol."""
    if ref in remaining_source_names and source_module != target_module:
        return source_module
    return None


def _compute_graph_edits(  # noqa: PLR0913
    workspace_root: Path,
    source_path: Path,
    target_path: Path,
    source_module: str,
    target_module: str,
    new_source_tree: cst.Module,
    new_target_tree: cst.Module,
    caller_texts: dict[Path, tuple[str, str]],
    internal_modules: set[str],
    graph: dict[str, set[str]],
    blocks: list[Any],
    source_tree: cst.Module,
) -> GraphEdits:
    """Diff the updated module imports against ``graph`` to produce ``GraphEdits``."""
    adds: list[tuple[str, str]] = []
    removes: list[tuple[str, str]] = []

    def _apply(mod_name: str, new_imps: set[str]) -> None:
        old_imps = graph.get(mod_name, set())
        for m in sorted(new_imps - old_imps):
            adds.append((mod_name, m))
        for m in sorted(old_imps - new_imps):
            removes.append((mod_name, m))

    _apply(
        source_module,
        _extract_absolute_imports(new_source_tree, internal_modules),
    )
    target_imports = _extract_absolute_imports(new_target_tree, internal_modules)
    target_imports |= _block_implied_target_imports(
        blocks,
        source_tree,
        new_source_tree,
        source_module,
        target_module,
        internal_modules,
    )
    _apply(target_module, target_imports)

    for caller_path, (_old_text, new_text) in caller_texts.items():
        try:
            caller_module = _module_path_from_file(caller_path, workspace_root)
        except ValueError:
            continue
        try:
            new_tree = cst.parse_module(new_text)
        except Exception:  # noqa: BLE001, S112
            continue
        _apply(
            caller_module,
            _extract_absolute_imports(new_tree, internal_modules),
        )

    # Imports no longer needed are not considered — the graph diff already
    # reflects them via _apply above.
    _ = source_path
    _ = target_path
    return GraphEdits(adds=adds, removes=removes)


def _cycle_check(  # noqa: PLR0913
    workspace_root: Path,
    source_path: Path,
    target_path: Path,
    new_source_tree: cst.Module,
    new_target_tree: cst.Module,
    caller_texts: dict[Path, tuple[str, str]],
    plan: MovePlan,
    blocks: list[Any],
    source_tree: cst.Module,
) -> list[str] | None:
    """Run intra-package cycle detection and return the new cycle chain if any.

    Returns ``None`` when no new cycle is introduced, when the move is
    cross-package (adds a skip-warning to ``plan``), or when the package
    layout is not discoverable (no-op).
    """
    src_pkg_root = _find_pkg_root(source_path, workspace_root)
    tgt_pkg_root = _find_pkg_root(target_path, workspace_root)
    if src_pkg_root is None or tgt_pkg_root is None:
        return None
    if src_pkg_root != tgt_pkg_root:
        plan.warnings.append(
            "Cross-package move \u2014 cycle detection skipped, verify manually"
        )
        return None

    try:
        source_module = _module_path_from_file(source_path, workspace_root)
        target_module = _module_path_from_file(target_path, workspace_root)
    except ValueError:
        return None

    graph, internal_modules = _build_current_graph(src_pkg_root)
    edits = _compute_graph_edits(
        workspace_root,
        source_path,
        target_path,
        source_module,
        target_module,
        new_source_tree,
        new_target_tree,
        caller_texts,
        internal_modules,
        graph,
        blocks,
        source_tree,
    )
    return detect_new_cycle(graph, edits)


def _inject_reexport(
    source_tree: cst.Module,
    new_module: str,
    moved_names: Sequence[str],
) -> cst.Module:
    """Append ``from new_module import <names>  # re-export …`` to ``source_tree``."""
    names_piece = ", ".join(moved_names)
    stmt = cst.parse_statement(
        f"from {new_module} import {names_piece}  # re-export for backwards compat\n"
    )
    return source_tree.with_changes(body=[*source_tree.body, stmt])


def _validate_options(
    shared_helpers: str,
    shared_helpers_module: str | None,
    reexport: bool,
    rename: dict[str, str] | None,
) -> None:
    if shared_helpers == "extract" or shared_helpers_module is not None:
        raise NotImplementedError("extract mode arrives in Phase 3")
    if reexport and rename is not None:
        raise ValueError("reexport=True is incompatible with rename=")


def _resolve_caller_phase(
    reexport: bool,
    root: Path,
    moved_names: Sequence[str],
    source_path: Path,
    target_path: Path,
) -> tuple[dict[Path, tuple[str, str]], list[CallerRewrite]]:
    if reexport:
        return {}, []
    return _process_callers(root, moved_names, source_path, target_path)


def _enforce_cycle(cycle: object, check: bool, dry_run: bool) -> None:
    if cycle is not None and (check or not dry_run):
        raise ImportCycleError(cycle)


def move_symbols(  # noqa: PLR0913
    source_path: str | Path,
    target_path: str | Path,
    symbol_names: Sequence[str],
    dry_run: bool = False,
    workspace_root: Path | None = None,
    shared_helpers: str = "duplicate",
    shared_helpers_module: str | None = None,
    reexport: bool = False,
    rename: dict[str, str] | None = None,
    check: bool = False,
) -> MovePlan:
    """Move top-level symbols from ``source_path`` to ``target_path``.

    Pipeline: parse → expand overloads → extract blocks → gather deps →
    build new target (imports + constants + symbols) → remove from source
    → classify shared helpers → validate parseability → atomic write via
    ``batch_edit`` → ruff fix.

    ``shared_helpers`` selects the strategy when a helper is used by both a
    moved symbol and a remaining source symbol: ``"duplicate"`` copies and
    keeps the helper (emitting a warning); ``"error"`` aborts with
    :class:`SharedHelpersError`; ``"extract"`` is reserved for Phase 3.

    When ``reexport=True``, callers are left untouched and a
    ``from new_module import <names>  # re-export for backwards compat`` line
    is appended to the source module. Incompatible with ``rename=``.

    When ``check=True``, the move is simulated (no files written) and any
    *newly introduced* import cycle raises :class:`ImportCycleError`. A
    normal (non-``dry_run``) write also performs this check; ``dry_run=True``
    alone preserves its historical "preview without enforcement" contract.
    """
    _validate_options(shared_helpers, shared_helpers_module, reexport, rename)

    source_path = Path(source_path)
    target_path = Path(target_path)

    source_text = source_path.read_text()
    target_text = target_path.read_text()
    source_tree = cst.parse_module(source_text)
    target_tree = cst.parse_module(target_text)

    expanded_names, moved_names = _validate_and_expand(
        source_tree, target_tree, symbol_names
    )
    remove_targets, blocks = _extract_moved_blocks(source_tree, expanded_names)
    (
        new_source_tree,
        new_target_tree,
        imports_added,
        constants_added,
        shared_map,
        redundant_import_warnings,
    ) = _build_trees(source_tree, target_tree, blocks, remove_targets, shared_helpers)

    root = (
        Path(workspace_root)
        if workspace_root is not None
        else _find_workspace_root(source_path)
    )

    if reexport:
        try:
            new_module_path = _module_path_from_file(target_path, root)
        except ValueError:
            new_module_path = target_path.stem
        new_source_tree = _inject_reexport(
            new_source_tree, new_module_path, moved_names
        )

    source_text_new, target_text_new = _render_and_validate(
        new_source_tree, new_target_tree
    )

    caller_texts, caller_rewrites = _resolve_caller_phase(
        reexport, root, moved_names, source_path, target_path
    )

    plan = _build_plan(
        source_text_new,
        target_text_new,
        moved_names,
        imports_added,
        constants_added,
        shared_map,
        callers_updated=caller_rewrites,
        redundant_import_warnings=redundant_import_warnings,
    )

    cycle = _cycle_check(
        root,
        source_path,
        target_path,
        new_source_tree,
        new_target_tree,
        caller_texts,
        plan,
        blocks,
        source_tree,
    )
    _enforce_cycle(cycle, check, dry_run)

    if dry_run or check:
        return plan

    _apply_write(
        source_path,
        target_path,
        source_text,
        target_text,
        source_text_new,
        target_text_new,
        workspace_root,
        caller_texts,
    )
    plan.warnings.extend(_ruff_fix(source_path, target_path, reexport=reexport))
    return plan
