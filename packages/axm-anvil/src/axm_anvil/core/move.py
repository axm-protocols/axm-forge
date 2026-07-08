"""Atomic move pipeline: relocate top-level symbols between modules."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import libcst as cst
from axm_ast import analyze_workspace, build_workspace_module_graph
from axm_ingot.uv import find_project_root
from libcst.codemod import CodemodContext
from libcst.codemod.visitors import AddImportsVisitor

from axm_anvil._cst.blocks import Block, _collect_refs, extract_blocks
from axm_anvil._cst.overloads import detect_overload_group
from axm_anvil._cst.transformers import (
    ProtectConditionalImports,
    RemoveSymbols,
    RenameSymbols,
    SyncDunderAll,
    _dump_attr,
)
from axm_anvil._cst.visitors import StringForwardRefScanner
from axm_anvil.core.callers import (
    CallerRewrite,
    _discover_callers,
    _discover_module_import_callers,
    _module_path_from_file,
    _rewrite_module_import_caller,
    rewrite_caller_text,
)
from axm_anvil.core.cycles import GraphEdits, detect_new_cycle
from axm_anvil.core.deps import (
    ImportInfo,
    _gather_target_existing,
    _gather_target_imports,
    gather_source_constants,
    gather_source_helpers,
    gather_source_imports,
    topo_sort_constants,
)
from axm_anvil.core.plan import (
    ImportCycleError,
    MovePathError,
    MovePlan,
    MoveValidationError,
    OverloadPartialMoveError,
    SharedHelperDetection,
    SharedHelpersError,
    SymbolAlreadyExistsError,
    SymbolNotFoundError,
)
from axm_anvil.core.postprocess import _ruff_fix
from axm_anvil.core.shared import SharedInfo, classify_shared_helpers

__all__ = [
    "PYTEST_BUILTIN_FIXTURES",
    "SIDE_EFFECT_DECORATORS",
    "ImportCycleError",
    "MovePathError",
    "MoveValidationError",
    "OverloadPartialMoveError",
    "SymbolAlreadyExistsError",
    "SymbolNotFoundError",
    "batch_edit",
    "detect_fixture_dependencies",
    "move_symbols",
]

# Fixtures pytest provides out of the box. A moved test referencing one of
# these never needs a ``conftest.py`` in scope, so they are excluded from the
# fixture-scope analysis. List per the pytest documentation (builtin fixtures).
PYTEST_BUILTIN_FIXTURES: frozenset[str] = frozenset(
    {
        "request",
        "tmp_path",
        "tmp_path_factory",
        "tmpdir",
        "tmpdir_factory",
        "monkeypatch",
        "capsys",
        "capfd",
        "capsysbinary",
        "capfdbinary",
        "caplog",
        "recwarn",
        "pytestconfig",
        "cache",
        "record_property",
        "doctest_namespace",
    }
)

# Decorator dotted-names that mark a function as a pytest fixture definition.
_PYTEST_FIXTURE_DECORATORS: frozenset[str] = frozenset({"pytest.fixture", "fixture"})

# Decorators whose primary purpose is to register the decorated symbol with an
# external registry as an import-time side effect. Moving such a symbol to a new
# module silently changes *where* (and whether) that registration runs, because
# the decorator only fires when the new module is imported. Each entry is the
# dotted form the decorator is conventionally written as; both the dotted form
# (``@pytest.fixture``) and its bare alias (``@fixture``) are listed so matching
# catches ``from pytest import fixture`` style imports too.
SIDE_EFFECT_DECORATORS: frozenset[str] = frozenset(
    {
        # Flask / FastAPI / Starlette route registration
        "app.route",
        "app.get",
        "app.post",
        "app.put",
        "app.delete",
        "app.patch",
        "router.get",
        "router.post",
        "router.put",
        "router.delete",
        "router.patch",
        # pytest fixture registration
        "pytest.fixture",
        "fixture",
        # Celery task registration
        "celery.task",
        "app.task",
        "shared_task",
        # Click command registration
        "click.command",
        "click.group",
        # functools single-dispatch registration
        "singledispatch",
        "functools.singledispatch",
    }
)


def _decorator_dotted_name(node: cst.BaseExpression) -> str | None:
    """Render a decorator expression to its dotted-name string.

    Handles bare names (``@fixture`` -> ``"fixture"``), dotted attribute
    chains (``@pytest.fixture`` -> ``"pytest.fixture"``) and call forms
    (``@app.route("/x")`` -> ``"app.route"``) by unwrapping the
    :class:`libcst.Call` and rendering its ``func``. Returns ``None`` for
    shapes that cannot be reduced to a dotted name.
    """
    if isinstance(node, cst.Call):
        node = node.func
    return _dump_attr(node)


def _side_effect_decorator_warnings(
    blocks: list[Block], whitelist: frozenset[str]
) -> list[str]:
    """Warn when a moved block carries a whitelisted side-effect decorator.

    Detection-only: reads ``.decorators`` from each block's
    ``FunctionDef``/``ClassDef`` node, renders each decorator to a dotted
    name and emits a structured warning when it matches ``whitelist``. The
    move itself is never blocked.
    """
    warnings: list[str] = []
    for block in blocks:
        node = block.node
        if not isinstance(node, cst.FunctionDef | cst.ClassDef):
            continue
        for decorator in node.decorators:
            dotted = _decorator_dotted_name(decorator.decorator)
            if dotted is not None and dotted in whitelist:
                warnings.append(
                    f"moved symbol '{block.name}' carries side-effect decorator "
                    f"'{dotted}'; registration may not run in the new module"
                )
    return warnings


def batch_edit(  # type: ignore[explicit-any]  # JSON-shape payload at axm-edit frontier
    path: str | Path, operations: list[dict[str, Any]]
) -> None:
    """Apply a batch of file operations atomically via ``axm-edit``.

    Accepts dict-shaped operations (``{op, file, edits|content}``) and
    delegates to :func:`axm_edit.core.engine.batch_apply`. Raises on any
    validation error so callers can trigger rollback.
    """
    from axm_edit.core.engine import batch_apply
    from axm_edit.models.operations import CreateOp, DeleteOp, Edit, ReplaceOp

    ops: list[CreateOp | DeleteOp | ReplaceOp] = []
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


def _parse_symbol_spec(spec: str) -> tuple[str, int | None]:
    if ":" in spec:
        name, idx = spec.split(":", 1)
        try:
            return name, int(idx)
        except ValueError:
            return spec, None
    return spec, None


def _reject_partial_overload(
    name: str, idx: int | None, group: list[cst.FunctionDef]
) -> None:
    if idx is not None and group:
        raise OverloadPartialMoveError(
            f"{name!r} is part of an overload group of {len(group)} "
            "signatures; move the full group by name without ':idx'"
        )


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
        group = detect_overload_group(source_tree, name)
        _reject_partial_overload(name, idx, group)
        if name in seen:
            continue
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
    blocks: list[Block],
    source_helpers: dict[str, cst.FunctionDef | cst.ClassDef],
    source_constants: dict[str, cst.SimpleStatementLine],
    include_helpers: bool = True,
) -> tuple[
    dict[str, cst.FunctionDef | cst.ClassDef],
    dict[str, cst.SimpleStatementLine],
    list[str],
]:
    """BFS transitive closure over helpers and constants from block refs.

    Returns collected helpers and constants in BFS-discovery order
    (dict insertion order) plus the list of local helper/constant names
    that were intentionally skipped. Stable on reference cycles.

    When ``include_helpers`` is ``False`` the BFS still discovers which
    local helpers/constants the moved blocks reference (so they can be
    surfaced as un-copied), but they are not collected into the target.
    Imports are gathered separately and are never suppressed.
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
    if not include_helpers:
        skipped = list(state.collected_helpers) + list(state.collected_constants)
        return {}, {}, skipped
    return state.collected_helpers, state.collected_constants, []


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
    blocks: list[Block],
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
    info: ImportInfo,
    imports_added: list[str],
) -> None:
    """Queue a flat (unconditional) import on ``context`` for the target tree.

    Relative ``from`` imports are emitted with their dot level preserved
    (``info.relative``); cross-package relatives are expected to have been
    rewritten to absolute (``relative == 0``) upstream by
    :func:`_resolve_copied_import`. The human-readable import label is
    appended to ``imports_added`` (de-duplicated). Conditional imports are
    handled separately via guard-block splicing, not here.
    """
    dots = "." * info.relative
    if info.obj is not None:
        AddImportsVisitor.add_needed_import(
            context, info.module, info.obj, asname=info.alias, relative=info.relative
        )
        label = f"from {dots}{info.module} import {info.obj}"
        if info.alias:
            label += f" as {info.alias}"
    else:
        AddImportsVisitor.add_needed_import(
            context, info.module, asname=info.alias, relative=info.relative
        )
        label = f"import {info.module}"
        if info.alias:
            label += f" as {info.alias}"
    if label not in imports_added:
        imports_added.append(label)


def _containing_pkg_parts(py: Path, pkg_root: Path) -> tuple[str, ...]:
    """Return the dotted parts of the *package* containing module ``py``.

    Drops the module's own final component from its absolute dotted path so
    that, e.g., ``src_pkg.source`` yields ``("src_pkg",)``.
    """
    parts = _pkg_module_name(py.resolve(), pkg_root.resolve()).split(".")
    return tuple(parts[:-1])


def _build_import_resolution(
    source_path: Path, target_path: Path, root: Path
) -> _ImportResolution | None:
    """Build the relative-import resolution context for a move.

    Returns ``None`` when either endpoint is not inside a package (no
    ``__init__.py`` ancestor), in which case relative imports cannot be
    resolved and are left to the historical drop behaviour.
    """
    source_pkg_root = _find_pkg_root(source_path, root)
    target_pkg_root = _find_pkg_root(target_path, root)
    if source_pkg_root is None or target_pkg_root is None:
        return None
    return _ImportResolution(
        source_pkg_parts=_containing_pkg_parts(source_path, source_pkg_root),
        target_pkg_parts=_containing_pkg_parts(target_path, target_pkg_root),
        same_package=source_pkg_root.resolve() == target_pkg_root.resolve(),
    )


@dataclass(frozen=True)
class _ImportResolution:
    """Package context for rewriting relative imports copied during a move.

    ``source_pkg_parts`` / ``target_pkg_parts`` are the dotted parts of the
    *containing package* of the source/target module (i.e. the module's
    absolute dotted path minus its final component). ``same_package`` is
    ``True`` when source and target share the same package root, in which
    case relative imports are preserved (re-leveled if the directory depth
    changed); otherwise they are converted to absolute imports.
    """

    source_pkg_parts: tuple[str, ...]
    target_pkg_parts: tuple[str, ...]
    same_package: bool


def _absolute_from_parts(
    info: ImportInfo, source_pkg_parts: tuple[str, ...]
) -> tuple[str, ...] | None:
    """Resolve a relative import to its absolute ``from``-module parts.

    A single leading dot resolves against the source module's own package;
    each extra dot walks up one more package. Returns ``None`` when the
    walk would go above the package root (unresolvable).
    """
    drop = info.relative - 1
    if drop > len(source_pkg_parts):
        return None
    kept = (
        source_pkg_parts[: len(source_pkg_parts) - drop] if drop else source_pkg_parts
    )
    module_parts = tuple(info.module.split(".")) if info.module else ()
    return kept + module_parts


def _resolve_copied_import(
    info: ImportInfo, resolution: _ImportResolution
) -> tuple[ImportInfo | None, str | None]:
    """Resolve a relative ``ImportInfo`` for copying into the target module.

    Returns ``(rewritten_info, warning)``. For an intra-package move the
    import is preserved/re-leveled and kept relative; for a cross-package
    move it is converted to an equivalent absolute import. Imported names
    and aliases are always preserved. When the relative import cannot be
    resolved (walks above the package root) ``(None, warning)`` is returned
    so no malformed import is written.
    """
    if not info.relative:
        return info, None
    abs_parts = _absolute_from_parts(info, resolution.source_pkg_parts)
    if abs_parts is None:
        return None, (
            f"unresolvable relative import: "
            f"{'.' * info.relative}{info.module} "
            f"(walks above package root) — not copied"
        )
    if not resolution.same_package:
        return (
            ImportInfo(
                module=".".join(abs_parts),
                obj=info.obj,
                alias=info.alias,
                relative=0,
            ),
            None,
        )
    return _relevel_intra_package(info, abs_parts, resolution.target_pkg_parts), None


def _relevel_intra_package(
    info: ImportInfo, abs_parts: tuple[str, ...], target_pkg_parts: tuple[str, ...]
) -> ImportInfo:
    """Recompute a relative import's dot level relative to the target package.

    When source and target live in the same directory this reproduces the
    original import verbatim; otherwise the dot level is adjusted so the
    import still points at the same absolute ``from``-module.
    """
    common = 0
    for a, b in zip(target_pkg_parts, abs_parts, strict=False):
        if a != b:
            break
        common += 1
    new_level = (len(target_pkg_parts) - common) + 1
    new_module = ".".join(abs_parts[common:])
    return ImportInfo(
        module=new_module,
        obj=info.obj,
        alias=info.alias,
        relative=new_level,
    )


def _import_modules_match(source_info: ImportInfo, target_info: ImportInfo) -> bool:
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


def _guard_code(guard: cst.BaseCompoundStatement) -> str:
    """Return the normalized source of a guard block for equivalence checks."""
    return cst.Module(body=[guard]).code.strip()


def _existing_guard_codes(target_tree: cst.Module) -> set[str]:
    """Return normalized source of every top-level ``Try``/``If`` guard."""
    return {
        _guard_code(stmt)
        for stmt in target_tree.body
        if isinstance(stmt, cst.Try | cst.If)
    }


def _is_docstring_stmt(stmt: cst.BaseStatement) -> bool:
    """Return ``True`` if ``stmt`` is a bare module/string-literal docstring line."""
    if not isinstance(stmt, cst.SimpleStatementLine) or not stmt.body:
        return False
    first = stmt.body[0]
    return isinstance(first, cst.Expr) and isinstance(
        first.value, cst.SimpleString | cst.ConcatenatedString
    )


def _is_future_import_stmt(stmt: cst.BaseStatement) -> bool:
    """Return ``True`` if ``stmt`` is a ``from __future__ import ...`` line."""
    if not isinstance(stmt, cst.SimpleStatementLine):
        return False
    return any(
        isinstance(small, cst.ImportFrom)
        and small.module is not None
        and _dotted_name_of(small.module) == "__future__"
        for small in stmt.body
    )


def _module_preamble_offset(tree: cst.Module) -> int:
    """Return the body index after the module docstring and ``__future__`` block.

    Guard blocks (``try: import ... except ImportError``) must be spliced
    *after* any leading module docstring — inserting at position 0 would demote
    the docstring to an ordinary string statement, nulling ``module.__doc__``
    and breaking E402. A ``from __future__ import`` line, when present, must
    also stay first, so it is skipped too.
    """
    body = tree.body
    offset = 1 if body and _is_docstring_stmt(body[0]) else 0
    while offset < len(body) and _is_future_import_stmt(body[offset]):
        offset += 1
    return offset


def _splice_guard_blocks(
    target_tree: cst.Module, guards: list[cst.BaseCompoundStatement]
) -> cst.Module:
    """Splice conditional guard blocks after the target's docstring/preamble."""
    if not guards:
        return target_tree
    seen = _existing_guard_codes(target_tree)
    to_add: list[cst.BaseStatement] = []
    for guard in guards:
        code = _guard_code(guard)
        if code in seen:
            continue
        seen.add(code)
        block = guard.with_changes(leading_lines=[cst.EmptyLine()])
        to_add.append(block)
    if not to_add:
        return target_tree
    offset = _module_preamble_offset(target_tree)
    body = list(target_tree.body)
    new_body = [*body[:offset], *to_add, *body[offset:]]
    return target_tree.with_changes(body=new_body)


def _apply_imports(
    target_tree: cst.Module,
    external_refs: set[str],
    source_imports: dict[str, ImportInfo],
    target_imports: dict[str, ImportInfo],
    import_resolution: _ImportResolution | None = None,
) -> tuple[cst.Module, list[str], list[str]]:
    context = CodemodContext()
    imports_added: list[str] = []
    redundant_warnings: list[str] = []
    conditional_guards: list[cst.BaseCompoundStatement] = []
    for name in sorted(external_refs):
        info = source_imports.get(name)
        if info is None:
            continue
        _classify_import(
            name,
            info,
            target_imports,
            import_resolution,
            context,
            imports_added,
            redundant_warnings,
            conditional_guards,
        )
    new_tree = AddImportsVisitor(context).transform_module(target_tree)
    new_tree = _splice_guard_blocks(new_tree, conditional_guards)
    return (
        new_tree,
        imports_added,
        redundant_warnings,
    )


def _classify_import(  # noqa: PLR0913
    name: str,
    info: ImportInfo,
    target_imports: dict[str, ImportInfo],
    import_resolution: _ImportResolution | None,
    context: CodemodContext,
    imports_added: list[str],
    redundant_warnings: list[str],
    conditional_guards: list[cst.BaseCompoundStatement],
) -> None:
    """Route a single source import into the target tree being assembled.

    Existing target imports short-circuit (emitting a redundancy warning on
    module mismatch); conditional imports defer to guard-block splicing;
    relative imports are resolved/converted via ``import_resolution``;
    everything else is queued as a flat import.
    """
    existing = target_imports.get(name)
    if existing is not None:
        if not _import_modules_match(info, existing):
            redundant_warnings.append(
                f"redundant import: {name} already imported from "
                f"{existing.module}; source had {info.module}"
            )
        return
    if info.conditional and info.guard is not None:
        conditional_guards.append(info.guard)
        label = f"conditional import block for {name}"
        if label not in imports_added:
            imports_added.append(label)
        return
    if info.relative:
        if import_resolution is None:
            return
        resolved, warning = _resolve_copied_import(info, import_resolution)
        if warning is not None:
            redundant_warnings.append(warning)
        if resolved is None:
            return
        info = resolved
    _register_import(context, info, imports_added)


def _build_constants_body(
    collected_constants: dict[str, cst.SimpleStatementLine],
    target_existing: set[str],
) -> tuple[list[cst.BaseStatement], list[str]]:
    body: list[cst.BaseStatement] = []
    constants_added: list[str] = []
    for stmt in topo_sort_constants(collected_constants):
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


def _build_blocks_body(blocks: list[Block]) -> list[cst.BaseStatement]:
    body: list[cst.BaseStatement] = []
    for block in blocks:
        new_node = block.node
        if hasattr(new_node, "with_changes"):
            new_node = new_node.with_changes(
                leading_lines=[cst.EmptyLine(), cst.EmptyLine()]
            )
        body.append(new_node)
    return body


def _stmt_top_name(stmt: cst.BaseStatement) -> str | None:
    """Return the top-level symbol name defined by ``stmt`` (or ``None``).

    Handles ``FunctionDef`` / ``ClassDef`` (``.name.value``) and simple
    assignment statements (mirrors :func:`_constant_name`).
    """
    if isinstance(stmt, cst.ClassDef | cst.FunctionDef):
        return stmt.name.value
    if isinstance(stmt, cst.SimpleStatementLine):
        return _constant_name(stmt)
    return None


def _splice_blocks_after_anchor(
    base_body: list[cst.BaseStatement],
    blocks_body: list[cst.BaseStatement],
    insert_after: str,
) -> tuple[list[cst.BaseStatement], list[str]]:
    """Insert ``blocks_body`` right after the ``insert_after`` anchor.

    When the anchor is not found, the blocks are appended at the end and a
    warning is returned. Returns ``(new_body, warnings)``.
    """
    for idx, stmt in enumerate(base_body):
        if _stmt_top_name(stmt) == insert_after:
            return (
                base_body[: idx + 1] + blocks_body + base_body[idx + 1 :],
                [],
            )
    warning = (
        f"insert_after target '{insert_after}' not found in target; appended at end"
    )
    return base_body + blocks_body, [warning]


def _build_target_tree(  # noqa: PLR0913
    target_tree: cst.Module,
    blocks: list[Block],
    source_imports: dict[str, ImportInfo],
    collected_constants: dict[str, cst.SimpleStatementLine],
    collected_helpers: dict[str, cst.FunctionDef | cst.ClassDef],
    source_helpers_order: list[str],
    insert_after: str | None = None,
    import_resolution: _ImportResolution | None = None,
) -> tuple[cst.Module, list[str], list[str], list[str]]:
    """Assemble the target module: imports + constants + helpers + blocks.

    Imports, constants and helpers keep their historical end-append
    placement; only the moved *blocks* honor ``insert_after``. When
    ``insert_after`` is ``None`` the blocks append at the end (unchanged
    contract). When it names a symbol absent from the assembled body the
    blocks append at the end and a warning is added to the returned list.

    Returns ``(new_tree, imports_added_labels, constants_added_names,
    redundant_import_warnings)``.
    """
    target_existing = _gather_target_existing(target_tree)
    target_imports = _gather_target_imports(target_tree)
    external_refs = _collect_external_refs(
        blocks, collected_helpers, collected_constants
    )
    tree_with_imports, imports_added, redundant_warnings = _apply_imports(
        target_tree, external_refs, source_imports, target_imports, import_resolution
    )
    constants_body, constants_added = _build_constants_body(
        collected_constants, target_existing
    )
    helpers_body = _build_helpers_body(
        source_helpers_order, collected_helpers, target_existing
    )
    blocks_body = _build_blocks_body(blocks)
    base_body = list(tree_with_imports.body) + constants_body + helpers_body
    if insert_after is None:
        new_body = base_body + blocks_body
    else:
        new_body, anchor_warnings = _splice_blocks_after_anchor(
            base_body, blocks_body, insert_after
        )
        redundant_warnings = redundant_warnings + anchor_warnings
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


def _is_dunder_all_assign(inner: cst.BaseSmallStatement) -> bool:
    if not isinstance(inner, cst.Assign) or len(inner.targets) != 1:
        return False
    target = inner.targets[0].target
    return isinstance(target, cst.Name) and target.value == "__all__"


def _string_elements(value: cst.BaseExpression) -> list[str]:
    if not isinstance(value, cst.List | cst.Tuple):
        return []
    return [
        element.value.raw_value
        for element in value.elements
        if isinstance(element, cst.Element)
        and isinstance(element.value, cst.SimpleString)
    ]


def _dunder_all_names(tree: cst.Module) -> list[str]:
    """Return the string names declared in a module-level ``__all__`` literal.

    Scans top-level ``SimpleStatementLine`` statements for an ``__all__``
    assignment whose value is a ``List``/``Tuple`` of string literals.
    Returns the names in declaration order, or an empty list when no such
    ``__all__`` literal exists.
    """
    for stmt in tree.body:
        if not isinstance(stmt, cst.SimpleStatementLine):
            continue
        for inner in stmt.body:
            if _is_dunder_all_assign(inner):
                return _string_elements(inner.value)  # type: ignore[attr-defined]
    return []


def _validate_and_expand(
    source_tree: cst.Module,
    target_tree: cst.Module,
    symbol_names: Sequence[str],
    strict: bool = False,
) -> tuple[list[str], list[str], list[str]]:
    """Expand overload aliases and validate presence in source / absence in target.

    Returns ``(present_expanded_names, present_moved_names, skipped_warnings)``.
    A name absent from the source module's top-level symbols is dropped from
    both name lists and reported via ``skipped_warnings`` — unless ``strict``
    is set, in which case the first absent name raises
    :class:`SymbolNotFoundError` (legacy behaviour).
    """
    expanded_names, moved_names = _expand_overloads(source_tree, symbol_names)

    expanded_names, moved_names, skipped_warnings = _drop_absent_symbols(
        source_tree, expanded_names, moved_names, strict
    )

    _assert_target_free(target_tree, expanded_names)

    return expanded_names, moved_names, skipped_warnings


def _extract_moved_blocks(
    source_tree: cst.Module, expanded_names: Sequence[str]
) -> tuple[set[str], list[Block]]:
    """Extract blocks (with overload groups expanded) and symbols to remove."""
    remove_targets: set[str] = set()
    blocks: list[Block] = []
    for name in expanded_names:
        group = detect_overload_group(source_tree, name)
        if group:
            for func in group:
                remove_targets.add(func.name.value)
            for func in group:
                blocks.append(
                    Block(
                        name=func.name.value,
                        node=func,
                        leading_lines=[],
                        referenced_names=_collect_refs(func, func.name.value),
                    )
                )
        else:
            remove_targets.add(name)
            extracted = extract_blocks(source_tree, [name])
            blocks.extend(extracted)
    return remove_targets, blocks


def _drop_absent_symbols(
    source_tree: cst.Module,
    expanded_names: list[str],
    moved_names: list[str],
    strict: bool,
) -> tuple[list[str], list[str], list[str]]:
    source_names = _source_symbol_names(source_tree)
    absent = [name for name in expanded_names if name not in source_names]
    if absent and strict:
        raise SymbolNotFoundError(absent[0])
    skipped = set(absent)
    skipped_warnings = [
        f"skipped '{name}': not a top-level symbol in source" for name in absent
    ]
    return (
        [name for name in expanded_names if name not in skipped],
        [name for name in moved_names if name not in skipped],
        skipped_warnings,
    )


def _assert_target_free(target_tree: cst.Module, names: list[str]) -> None:
    target_existing = _gather_target_existing(target_tree)
    for name in names:
        if name in target_existing:
            raise SymbolAlreadyExistsError(name)


def _assert_rename_targets_free(
    target_tree: cst.Module, rename_map: dict[str, str]
) -> None:
    """Reject a move whose *renamed* name already exists in the target.

    ``_validate_and_expand`` only checks the pre-rename names against the
    target; a ``rename={'foo': 'bar'}`` where ``bar`` is already defined in
    the target would otherwise write a second ``def bar`` that silently
    shadows the first at import. Guard against that renamed-target collision.
    """
    target_existing = _gather_target_existing(target_tree)
    for new_name in rename_map.values():
        if new_name in target_existing:
            raise SymbolAlreadyExistsError(new_name)


def _resolve_shared_map(
    blocks: list[Block],
    collected_helpers: dict[str, cst.FunctionDef | cst.ClassDef],
    new_source_tree: cst.Module,
    include_helpers: bool,
    shared_helpers: str,
) -> dict[str, SharedInfo]:
    if not include_helpers:
        return {}
    shared_map = classify_shared_helpers(
        blocks, set(collected_helpers.keys()), new_source_tree
    )
    if shared_map and shared_helpers == "error":
        raise SharedHelpersError(sorted(shared_map.keys()))
    return shared_map


def _sync_dunder_all_trees(
    source_tree: cst.Module,
    new_source_tree: cst.Module,
    new_target_tree: cst.Module,
    remove_targets: set[str],
    rename_map: dict[str, str] | None,
) -> tuple[cst.Module, cst.Module]:
    ordered = [n for n in _dunder_all_names(source_tree) if n in remove_targets]
    if not ordered:
        return new_source_tree, new_target_tree
    exported = set(ordered)
    # Source removal keys on the *original* exported names; the target
    # append must use the *post-rename* names (AXM-1773 x AXM-1770).
    renames = rename_map or {}
    added = [renames.get(name, name) for name in ordered]
    new_source_tree = new_source_tree.visit(SyncDunderAll(exported, []))
    new_target_tree = new_target_tree.visit(SyncDunderAll(set(), added))
    return new_source_tree, new_target_tree


def _build_trees(  # noqa: PLR0913
    source_tree: cst.Module,
    target_tree: cst.Module,
    blocks: list[Block],
    remove_targets: set[str],
    shared_helpers: str,
    insert_after: str | None = None,
    include_helpers: bool = True,
    import_resolution: _ImportResolution | None = None,
    rename_map: dict[str, str] | None = None,
) -> tuple[
    cst.Module, cst.Module, list[str], list[str], dict[str, SharedInfo], list[str]
]:
    """Build new source/target trees and return added imports/constants + shared map.

    When ``include_helpers`` is ``False`` transitively-referenced local
    helpers/constants are not copied into the target, shared-helper
    classification is short-circuited, and a warning enumerating the
    skipped local helper names is appended to the returned warnings list.
    """
    source_imports = gather_source_imports(source_tree)
    source_constants = gather_source_constants(source_tree)
    source_helpers = gather_source_helpers(source_tree)

    collected_helpers, collected_constants, skipped_helpers = _collect_transitive_deps(
        blocks, source_helpers, source_constants, include_helpers
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
        insert_after=insert_after,
        import_resolution=import_resolution,
    )

    new_source_tree = source_tree.visit(RemoveSymbols(remove_targets))

    shared_map = _resolve_shared_map(
        blocks, collected_helpers, new_source_tree, include_helpers, shared_helpers
    )
    if skipped_helpers:
        redundant_import_warnings = [
            *redundant_import_warnings,
            "include_helpers=False: not copied into target: "
            + ", ".join(skipped_helpers),
        ]

    orphans = _compute_source_orphans(
        new_source_tree,
        set(collected_helpers.keys()),
        set(collected_constants.keys()),
    )
    orphans -= set(shared_map.keys())
    if orphans:
        new_source_tree = new_source_tree.visit(RemoveSymbols(orphans))

    new_source_tree, new_target_tree = _sync_dunder_all_trees(
        source_tree, new_source_tree, new_target_tree, remove_targets, rename_map
    )

    # AXM-1775 AC3: conditional imports (top-level try/except, if guards) must
    # never be removed from the source — the post-move ruff F401 pass would
    # otherwise strip a fallback branch and silently change runtime behavior.
    if any(info.conditional for info in source_imports.values()):
        new_source_tree = new_source_tree.visit(ProtectConditionalImports())

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
    shared_map: dict[str, SharedInfo],
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
    rename_map: dict[str, str] | None = None,
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
        result = _rewrite_one_caller(
            original, from_module, new_module, moved_names, rename_map
        )
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
    rename_map: dict[str, str] | None = None,
) -> tuple[str, list[CallerRewrite]] | None:
    """Apply both rewrites and validate the result. Returns ``None`` if unchanged."""
    try:
        current_text, from_rewrites = rewrite_caller_text(
            original, from_module, new_module, moved_names
        )
        current_text, attr_rewrites = _rewrite_module_import_caller(
            current_text, from_module, new_module, moved_names
        )
        if rename_map:
            current_text = _apply_rename_to_text(current_text, rename_map)
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
        else find_project_root(source_path)
    )
    try:
        source_rel = source_path.resolve().relative_to(root.resolve())
        target_rel = target_path.resolve().relative_to(root.resolve())
    except ValueError:
        # Cross-folder / cross-package move: ``target_path`` is not under the
        # resolved workspace root. Re-anchor on a base that actually contains
        # *both* paths instead of ``source_path.parent`` (which never contains
        # the target for a cross-folder move and raised a second ValueError).
        root = _common_base(source_path, target_path)
        source_rel = source_path.resolve().relative_to(root)
        target_rel = target_path.resolve().relative_to(root)

    operations: list[dict[str, Any]] = [  # type: ignore[explicit-any]  # JSON-shape payload at axm-edit frontier
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


def _common_base(source_path: Path, target_path: Path) -> Path:
    """Return a resolved directory that contains both ``source`` and ``target``.

    Used as the ``relative_to`` anchor for the ``batch_edit`` operations when
    the workspace root does not contain the target (cross-folder or
    cross-package move). Raises :class:`MovePathError` when the two paths have
    no usable common ancestor (e.g. different drives on Windows).
    """
    source = source_path.resolve()
    target = target_path.resolve()
    try:
        return Path(os.path.commonpath([source, target]))
    except ValueError as exc:
        raise MovePathError(source, target) from exc


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
    blocks: list[Block],
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
    source_imports = gather_source_imports(source_tree)
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


@dataclass(frozen=True)
class _GraphEditContext:
    """Shared inputs for diffing updated module imports against a graph."""

    source_module: str
    target_module: str
    new_source_tree: cst.Module
    new_target_tree: cst.Module
    caller_texts: dict[Path, tuple[str, str]]
    internal_modules: set[str]
    graph: dict[str, set[str]]
    blocks: list[Block]
    source_tree: cst.Module


def _diff_module_imports(
    ctx: _GraphEditContext,
    resolve_caller: Callable[[Path], str | None],
) -> GraphEdits:
    """Diff updated module imports against ``ctx.graph`` to produce ``GraphEdits``."""
    adds: list[tuple[str, str]] = []
    removes: list[tuple[str, str]] = []

    def _apply(mod_name: str, new_imps: set[str]) -> None:
        old_imps = ctx.graph.get(mod_name, set())
        for m in sorted(new_imps - old_imps):
            adds.append((mod_name, m))
        for m in sorted(old_imps - new_imps):
            removes.append((mod_name, m))

    _apply(
        ctx.source_module,
        _extract_absolute_imports(ctx.new_source_tree, ctx.internal_modules),
    )
    target_imports = _extract_absolute_imports(
        ctx.new_target_tree, ctx.internal_modules
    )
    target_imports |= _block_implied_target_imports(
        ctx.blocks,
        ctx.source_tree,
        ctx.new_source_tree,
        ctx.source_module,
        ctx.target_module,
        ctx.internal_modules,
    )
    _apply(ctx.target_module, target_imports)

    for caller_path, (_old_text, new_text) in ctx.caller_texts.items():
        caller_module = resolve_caller(caller_path)
        if caller_module is None:
            continue
        try:
            new_tree = cst.parse_module(new_text)
        except Exception:  # noqa: BLE001, S112
            continue
        _apply(
            caller_module,
            _extract_absolute_imports(new_tree, ctx.internal_modules),
        )

    return GraphEdits(adds=adds, removes=removes)


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
    blocks: list[Block],
    source_tree: cst.Module,
) -> GraphEdits:
    """Diff the updated module imports against ``graph`` to produce ``GraphEdits``."""
    _ = source_path
    _ = target_path

    def _resolve_caller(caller_path: Path) -> str | None:
        try:
            return _module_path_from_file(caller_path, workspace_root)
        except ValueError:
            return None

    ctx = _GraphEditContext(
        source_module=source_module,
        target_module=target_module,
        new_source_tree=new_source_tree,
        new_target_tree=new_target_tree,
        caller_texts=caller_texts,
        internal_modules=internal_modules,
        graph=graph,
        blocks=blocks,
        source_tree=source_tree,
    )
    return _diff_module_imports(ctx, _resolve_caller)


def _cycle_check(  # noqa: PLR0913
    workspace_root: Path,
    source_path: Path,
    target_path: Path,
    new_source_tree: cst.Module,
    new_target_tree: cst.Module,
    caller_texts: dict[Path, tuple[str, str]],
    blocks: list[Block],
    source_tree: cst.Module,
) -> list[str] | None:
    """Detect a newly-introduced import cycle and return its chain if any.

    Intra-package moves diff against the single-package graph; cross-package
    moves diff against the workspace-wide namespaced graph. Returns ``None``
    when no new cycle is introduced or when the package layout is not
    discoverable (no-op).
    """
    src_pkg_root = _find_pkg_root(source_path, workspace_root)
    tgt_pkg_root = _find_pkg_root(target_path, workspace_root)
    if src_pkg_root is None or tgt_pkg_root is None:
        return None
    if src_pkg_root != tgt_pkg_root:
        return _cross_package_cycle_check(
            workspace_root,
            source_path,
            target_path,
            src_pkg_root,
            tgt_pkg_root,
            new_source_tree,
            new_target_tree,
            caller_texts,
            blocks,
            source_tree,
        )

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


def _cross_package_cycle_check(  # noqa: PLR0913
    workspace_root: Path,
    source_path: Path,
    target_path: Path,
    src_pkg_root: Path,
    tgt_pkg_root: Path,
    new_source_tree: cst.Module,
    new_target_tree: cst.Module,
    caller_texts: dict[Path, tuple[str, str]],
    blocks: list[Block],
    source_tree: cst.Module,
) -> list[str] | None:
    """Detect a newly-introduced *cross-package* import cycle on a move.

    Builds the workspace-wide module graph (nodes namespaced as
    ``{import_pkg}.{module}`` by :func:`build_workspace_module_graph`) and
    computes ``GraphEdits`` in the *same* namespaced coordinates so
    :func:`detect_new_cycle` sees a connected node set. Returns the new
    cycle chain, or ``None`` when the move introduces no new cycle.
    """
    try:
        ws = analyze_workspace(workspace_root)
    except (OSError, ValueError):
        return None
    graph: dict[str, set[str]] = {
        k: set(v) for k, v in build_workspace_module_graph(ws).items()
    }
    internal_modules = set(graph)

    source_module = _pkg_module_name(source_path.resolve(), src_pkg_root)
    target_module = _pkg_module_name(target_path.resolve(), tgt_pkg_root)

    edits = _compute_workspace_graph_edits(
        workspace_root,
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


def _namespaced_caller_module(caller_path: Path, workspace_root: Path) -> str | None:
    """Namespace a caller file as ``{import_pkg}.{module}`` for the WS graph."""
    pkg_root = _find_pkg_root(caller_path, workspace_root)
    if pkg_root is None:
        return None
    return _pkg_module_name(caller_path.resolve(), pkg_root)


def _compute_workspace_graph_edits(  # noqa: PLR0913
    workspace_root: Path,
    source_module: str,
    target_module: str,
    new_source_tree: cst.Module,
    new_target_tree: cst.Module,
    caller_texts: dict[Path, tuple[str, str]],
    internal_modules: set[str],
    graph: dict[str, set[str]],
    blocks: list[Block],
    source_tree: cst.Module,
) -> GraphEdits:
    """Cross-package variant of :func:`_compute_graph_edits`.

    Identical edge-diff logic, but every module node is namespaced
    ``{import_pkg}.{module}`` and ``internal_modules`` is the full set of
    workspace graph nodes, so cross-package edges resolve correctly.
    """

    def _resolve_caller(caller_path: Path) -> str | None:
        return _namespaced_caller_module(caller_path, workspace_root)

    ctx = _GraphEditContext(
        source_module=source_module,
        target_module=target_module,
        new_source_tree=new_source_tree,
        new_target_tree=new_target_tree,
        caller_texts=caller_texts,
        internal_modules=internal_modules,
        graph=graph,
        blocks=blocks,
        source_tree=source_tree,
    )
    return _diff_module_imports(ctx, _resolve_caller)


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


def _active_rename(
    rename: dict[str, str] | None, moved_names: Sequence[str]
) -> dict[str, str]:
    """Restrict ``rename`` to names actually moved (skip absent/no-op entries)."""
    if not rename:
        return {}
    moved = set(moved_names)
    return {
        old: new for old, new in rename.items() if old in moved and new and new != old
    }


def _apply_rename_to_blocks(
    blocks: list[Block], rename_map: dict[str, str]
) -> list[Block]:
    """Rename moved block definitions (and their internal refs) to new names."""
    renamed: list[Block] = []
    transformer = RenameSymbols(rename_map)
    for block in blocks:
        new_name = rename_map.get(block.name, block.name)
        new_node = cast("cst.BaseStatement", block.node.visit(transformer))
        renamed.append(
            Block(
                name=new_name,
                node=new_node,
                leading_lines=block.leading_lines,
                referenced_names=block.referenced_names,
            )
        )
    return renamed


def _apply_rename_to_text(text: str, rename_map: dict[str, str]) -> str:
    """Apply an ``old -> new`` identifier rename across a rendered module."""
    return cst.parse_module(text).visit(RenameSymbols(rename_map)).code


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


def _function_defs_in_block(block: Block) -> list[cst.FunctionDef]:
    """Collect the function definitions carried by a moved ``block``.

    A function block contributes its own ``FunctionDef``; a class block
    contributes the ``FunctionDef`` methods nested directly in its body.
    """
    node = block.node
    if isinstance(node, cst.FunctionDef):
        return [node]
    if isinstance(node, cst.ClassDef):
        return [stmt for stmt in node.body.body if isinstance(stmt, cst.FunctionDef)]
    return []


def _is_fixture_consuming_function(func: cst.FunctionDef) -> bool:
    """Return ``True`` when ``func`` is a ``test_*`` or fixture-decorated def.

    These are the only functions whose parameters resolve against the pytest
    fixture namespace; plain helpers take ordinary arguments.
    """
    if func.name.value.startswith("test_"):
        return True
    for decorator in func.decorators:
        dotted = _decorator_dotted_name(decorator.decorator)
        if dotted in _PYTEST_FIXTURE_DECORATORS:
            return True
    return False


def _candidate_fixture_params(func: cst.FunctionDef) -> set[str]:
    """Return parameter names of ``func`` eligible to be fixtures.

    Excludes ``self``/``cls`` and any parameter carrying a default value
    (defaulted params are ordinary arguments, never fixtures).
    """
    names: set[str] = set()
    for param in func.params.params:
        name = param.name.value
        if name in {"self", "cls"}:
            continue
        if param.default is not None:
            continue
        names.add(name)
    return names


def detect_fixture_dependencies(blocks: list[Block], local_names: set[str]) -> set[str]:
    """Return the pytest fixture names a set of moved ``blocks`` depend on.

    A fixture dependency is a parameter name on a ``def test_*`` function or a
    ``@pytest.fixture``-decorated function (including methods of a moved
    class), excluding ``self``/``cls``, defaulted parameters, the pytest
    builtin fixtures in :data:`PYTEST_BUILTIN_FIXTURES`, and any name already
    resolvable as a local definition or import (``local_names``). Pure,
    in-memory CST analysis; no filesystem access.
    """
    used: set[str] = set()
    for block in blocks:
        for func in _function_defs_in_block(block):
            if not _is_fixture_consuming_function(func):
                continue
            for name in _candidate_fixture_params(func):
                if name in PYTEST_BUILTIN_FIXTURES or name in local_names:
                    continue
                used.add(name)
    return used


def _module_local_names(tree: cst.Module) -> set[str]:
    """Collect top-level definition and import names declared in ``tree``.

    Used to exclude parameter names that are satisfied by a local symbol or
    an import rather than a fixture.
    """
    names: set[str] = set()
    for stmt in tree.body:
        if isinstance(stmt, cst.FunctionDef | cst.ClassDef):
            names.add(stmt.name.value)
            continue
        if isinstance(stmt, cst.SimpleStatementLine):
            for small in stmt.body:
                names |= _names_from_small_stmt(small)
    return names


def _names_from_small_stmt(small: cst.BaseSmallStatement) -> set[str]:
    """Extract bound names from an assignment or import statement."""
    if isinstance(small, cst.Assign):
        return {t.target.value for t in small.targets if isinstance(t.target, cst.Name)}
    if isinstance(small, cst.AnnAssign) and isinstance(small.target, cst.Name):
        return {small.target.value}
    if isinstance(small, cst.Import | cst.ImportFrom):
        return _imported_aliases(small)
    return set()


def _imported_aliases(node: cst.Import | cst.ImportFrom) -> set[str]:
    """Return the local binding names introduced by an import statement."""
    if isinstance(node.names, cst.ImportStar):
        return set()
    names: set[str] = set()
    for alias in node.names:
        if alias.asname is not None and isinstance(alias.asname.name, cst.Name):
            names.add(alias.asname.name.value)
        elif isinstance(alias.name, cst.Name):
            names.add(alias.name.value)
        elif isinstance(alias.name, cst.Attribute):
            names.add(_leftmost_attr_name(alias.name))
    return names


def _leftmost_attr_name(attr: cst.Attribute) -> str:
    """Return the leftmost identifier of a dotted ``import a.b.c`` name."""
    node: cst.BaseExpression = attr
    while isinstance(node, cst.Attribute):
        node = node.value
    return node.value if isinstance(node, cst.Name) else ""


def _conftest_fixture_names(conftest: Path) -> set[str]:
    """Parse ``conftest`` and return the names of its ``@pytest.fixture`` defs."""
    try:
        tree = cst.parse_module(conftest.read_text())
    except (OSError, cst.ParserSyntaxError):
        return set()
    names: set[str] = set()
    for stmt in tree.body:
        if isinstance(stmt, cst.FunctionDef) and any(
            _decorator_dotted_name(d.decorator) in _PYTEST_FIXTURE_DECORATORS
            for d in stmt.decorators
        ):
            names.add(stmt.name.value)
    return names


def _resolve_fixture_conftest(fixture: str, from_file: Path, root: Path) -> Path | None:
    """Walk up from ``from_file`` to the nearest ``conftest.py`` defining
    ``fixture``; return its directory or ``None`` if unresolved within ``root``.
    """
    current = from_file.resolve().parent
    root_resolved = root.resolve()
    while True:
        conftest = current / "conftest.py"
        if conftest.is_file() and fixture in _conftest_fixture_names(conftest):
            return current
        if current == root_resolved:
            break
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def _fixture_scope_warnings(
    blocks: list[Block],
    source_tree: cst.Module,
    source_path: Path,
    target_path: Path,
    root: Path,
) -> list[str]:
    """Warn when a moved test's fixture falls out of conftest scope.

    Detection-only (real filesystem I/O): detects the fixture dependencies of
    the moved test blocks, resolves each to the nearest providing
    ``conftest.py`` by walking up from ``source_path``, and emits a structured
    warning when ``target_path`` is not within that conftest's directory
    subtree (``Path.is_relative_to``). The move itself is never blocked.
    """
    local_names = _module_local_names(source_tree)
    used = detect_fixture_dependencies(blocks, local_names)
    if not used:
        return []
    target_dir = target_path.resolve().parent
    warnings: list[str] = []
    for fixture in sorted(used):
        conftest_dir = _resolve_fixture_conftest(fixture, source_path, root)
        if conftest_dir is None:
            continue
        if not target_dir.is_relative_to(conftest_dir):
            warnings.append(
                f"moved test depends on fixture '{fixture}' provided by "
                f"'{conftest_dir / 'conftest.py'}'; the target is outside that "
                f"conftest's scope, so the fixture will be unresolved after the "
                f"move"
            )
    return warnings


def _string_forward_ref_warnings(
    source_tree: cst.Module, moved_names: Sequence[str]
) -> list[str]:
    """Detect string annotations that forward-reference a moved symbol.

    Detection-only: scans ``source_tree`` for string annotations whose
    parsed content names a moved symbol (whole-identifier match) and
    returns structured, actionable warnings. The tree is never mutated.
    """
    if not moved_names:
        return []
    scanner = StringForwardRefScanner(set(moved_names))
    source_tree.visit(scanner)
    return scanner.warnings


def _resolve_caller_phase(  # noqa: PLR0913
    reexport: bool,
    root: Path,
    moved_names: Sequence[str],
    source_path: Path,
    target_path: Path,
    rename_map: dict[str, str] | None = None,
) -> tuple[dict[Path, tuple[str, str]], list[CallerRewrite]]:
    if reexport:
        return {}, []
    return _process_callers(root, moved_names, source_path, target_path, rename_map)


def _enforce_cycle(cycle: list[str] | None, check: bool, dry_run: bool) -> None:
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
    strict: bool = False,
    insert_after: str | None = None,
    include_helpers: bool = True,
    side_effect_decorators: frozenset[str] | None = None,
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

    A requested name that is absent from the source module's top-level
    symbols is **skipped** with a warning on :attr:`MovePlan.warnings`
    rather than aborting the whole plan. Pass ``strict=True`` to restore
    the legacy behaviour of raising :class:`SymbolNotFoundError` on the
    first absent name.

    ``insert_after`` controls where the moved *blocks* land in the target
    module body: when it names an existing top-level symbol the blocks are
    spliced immediately after it; when ``None`` (default) the blocks append
    at the end (unchanged contract); when it names an absent symbol the
    blocks append at the end and a warning is added to
    :attr:`MovePlan.warnings`. Imports and constants keep their historical
    placement regardless of ``insert_after``.

    ``include_helpers`` (default ``True``) preserves the historical
    behaviour of copying transitively-referenced local helpers and
    constants into the target. When ``False`` those helpers/constants are
    **not** copied (the moved code is left referencing them), a warning
    enumerating the un-copied local helper names is added to
    :attr:`MovePlan.warnings`, and the ``shared_helpers`` classification is
    short-circuited (nothing is duplicated or extracted). Imports required
    by the moved code are always copied regardless of this flag.
    """
    _validate_options(shared_helpers, shared_helpers_module, reexport, rename)

    source_path = Path(source_path)
    target_path = Path(target_path)

    source_text = source_path.read_text()
    target_text = target_path.read_text()
    source_tree = cst.parse_module(source_text)
    target_tree = cst.parse_module(target_text)

    expanded_names, moved_names, skipped_warnings = _validate_and_expand(
        source_tree, target_tree, symbol_names, strict=strict
    )
    if not moved_names:
        # Nothing resolved to a present symbol (all absent, non-strict): the
        # move is a no-op. Return an empty plan with the original texts BEFORE
        # any tree-building or write, so source and target stay byte-identical.
        noop_plan = _build_plan(
            source_text,
            target_text,
            moved_names,
            [],
            [],
            {},
        )
        noop_plan.warnings.extend(skipped_warnings)
        return noop_plan
    remove_targets, blocks = _extract_moved_blocks(source_tree, expanded_names)
    rename_map = _active_rename(rename, moved_names)
    if rename_map:
        _assert_rename_targets_free(target_tree, rename_map)
        blocks = _apply_rename_to_blocks(blocks, rename_map)

    root = (
        Path(workspace_root)
        if workspace_root is not None
        else find_project_root(source_path)
    )
    import_resolution = _build_import_resolution(source_path, target_path, root)

    (
        new_source_tree,
        new_target_tree,
        imports_added,
        constants_added,
        shared_map,
        redundant_import_warnings,
    ) = _build_trees(
        source_tree,
        target_tree,
        blocks,
        remove_targets,
        shared_helpers,
        insert_after=insert_after,
        include_helpers=include_helpers,
        import_resolution=import_resolution,
        rename_map=rename_map,
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
        reexport, root, moved_names, source_path, target_path, rename_map
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
    plan.warnings.extend(skipped_warnings)
    # Forward-refs to *renamed* symbols are rewritten in the moved code
    # (RenameSymbols.leave_Annotation); only moved-but-not-renamed names still
    # warrant the manual-update warning.
    unrenamed_moved = [n for n in moved_names if n not in rename_map]
    plan.warnings.extend(_string_forward_ref_warnings(source_tree, unrenamed_moved))
    deco_whitelist = SIDE_EFFECT_DECORATORS | (side_effect_decorators or frozenset())
    plan.warnings.extend(_side_effect_decorator_warnings(blocks, deco_whitelist))
    plan.warnings.extend(
        _fixture_scope_warnings(blocks, source_tree, source_path, target_path, root)
    )

    cycle = _cycle_check(
        root,
        source_path,
        target_path,
        new_source_tree,
        new_target_tree,
        caller_texts,
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
