"""Stage executors: apply ``FileOp``s to disk.

One executor per ``FileOp.kind`` (flatten/relocate/rename/split/merge)
plus the ``execute()`` dispatcher used by the pipeline loop. Each
executor returns a list of human-readable warnings; mutation happens
through ``cst_rewrite`` (in-file edits) and ``layout_and_move``
(file moves + cross-file rewrites).
"""

from __future__ import annotations

import ast
from pathlib import Path

import libcst as cst

try:
    from axm_anvil.core.move import move_symbols
except ImportError:  # pragma: no cover
    move_symbols = None  # type: ignore[assignment]

from .cst_rewrite import (
    _backfill_missing_imports,
    _delete_source_if_empty_tests,
    _flatten_class_to_top_level,
    _patch_file_dunder_depth,
    _reorder_module_statements,
)
from .findings import (
    _class_needs_flatten,
    _load_project_scripts,
    _per_unit_canonical,
    get_pkg_prefixes,
)
from .io_primitives import _cst_load, _cst_save, _git_mv
from .layout_and_move import (
    _rewrite_cross_test_imports,
    _safe_move_units,
)
from .models import FileOp
from .paths import (
    _file_depth_from_project,
    _module_path_for_test_file,
    _tier_for_path,
)
from .tests_ast import (
    _marker_fixtures_in_unit,
    _movable_units_at_top_level,
    _string_literal_fixtures_in_unit,
    _top_level_test_classes,
)

__all__ = [
    "_execute_flatten",
    "_execute_merge",
    "_execute_relocate",
    "_execute_rename",
    "_execute_split",
    "_reroute_through_safe_move",
    "execute",
]


def _execute_flatten(op: FileOp, project_path: Path) -> list[str]:
    """Flatten the listed Test* classes in op.source.

    Skips pathological cases (op.split_map is None — signaled by planner).
    """
    if op.split_map is None:
        return [f"flatten skipped: {op.rationale} ({op.source.name})"]
    if not op.source.exists():
        return [f"flatten skipped: {op.source} missing"]
    text = op.source.read_text()
    for class_name in op.split_map.keys():
        text = _flatten_class_to_top_level(text, class_name)
    op.source.write_text(text)
    _reorder_module_statements(op.source)
    return [f"flatten: rewrote {op.source.name} ({list(op.split_map.keys())})"]


def _reroute_through_safe_move(
    kind: str,
    source: Path,
    target: Path,
    project_path: Path,
) -> list[str]:
    """Common path for RELOCATE/RENAME when target already exists.

    Moves *source*'s units into the pre-existing *target* via
    ``_safe_move_units`` (handles helper-body collisions, conftest
    shadowing, marker fixtures), then deletes source if empty.
    """
    if not source.exists():
        return [f"{kind} skipped: source missing ({source})"]
    warnings: list[str] = [
        f"{kind}: target {target.name} already exists; "
        f"re-routing {source.name} through _safe_move_units"
    ]
    old_mod = _module_path_for_test_file(source, project_path)
    new_mod = _module_path_for_test_file(target, project_path)
    tree = ast.parse(source.read_text())
    units = _movable_units_at_top_level(tree)
    if units:
        sub_warnings, _ = _safe_move_units(source, target, units, project_path)
        warnings.extend(sub_warnings)
    _delete_source_if_empty_tests(source)
    if old_mod and new_mod and old_mod != new_mod and not source.exists():
        warnings.extend(
            _rewrite_cross_test_imports(
                project_path,
                old_mod,
                [new_mod],
                skip_paths={source, target},
            )
        )
    return warnings


def _execute_relocate(op: FileOp, project_path: Path) -> list[str]:
    """RELOCATE op: ``git mv`` between pyramid tiers.

    Same collision risk as ``_execute_rename``: a target file may
    already exist (different package mapping happens to land on the
    same path). Route through ``_safe_move_units`` rather than letting
    ``_git_mv`` overwrite. The fallback ``FileExistsError`` catch
    handles the race where another op in the same iteration created the
    target between the upfront check and the ``_git_mv`` call.
    """
    assert isinstance(op.target, Path)
    if op.target.exists() and op.target != op.source:
        return _reroute_through_safe_move(
            "relocate",
            op.source,
            op.target,
            project_path,
        )
    old_mod = _module_path_for_test_file(op.source, project_path)
    new_mod = _module_path_for_test_file(op.target, project_path)
    src_depth = _file_depth_from_project(op.source, project_path)
    tgt_depth = _file_depth_from_project(op.target, project_path)
    try:
        _git_mv(op.source, op.target)
    except FileExistsError:
        return _reroute_through_safe_move(
            "relocate",
            op.source,
            op.target,
            project_path,
        )
    warnings = []
    depth_delta = tgt_depth - src_depth
    if depth_delta != 0:
        warnings.extend(_patch_file_dunder_depth(op.target, depth_delta))
    if old_mod and new_mod and old_mod != new_mod:
        warnings.extend(
            _rewrite_cross_test_imports(
                project_path,
                old_mod,
                [new_mod],
                skip_paths={op.source, op.target},
            )
        )
    return warnings


def _execute_rename(op: FileOp, project_path: Path) -> list[str]:
    """RENAME op: ``git mv`` the source file to its canonical name.

    When ``op.target`` already exists (typical when a prior SPLIT/MERGE
    stage created the canonical destination), a naive ``git mv`` would
    overwrite it and silently destroy the merged tests. Route through
    ``_safe_move_units`` instead — the residual source's units are
    moved into the existing target, then the source is deleted. The
    ``FileExistsError`` catch handles the same race as RELOCATE.
    """
    assert isinstance(op.target, Path)
    if op.target.exists() and op.target != op.source:
        return _reroute_through_safe_move(
            "rename",
            op.source,
            op.target,
            project_path,
        )
    old_mod = _module_path_for_test_file(op.source, project_path)
    new_mod = _module_path_for_test_file(op.target, project_path)
    src_depth = _file_depth_from_project(op.source, project_path)
    tgt_depth = _file_depth_from_project(op.target, project_path)
    try:
        _git_mv(op.source, op.target)
    except FileExistsError:
        return _reroute_through_safe_move(
            "rename",
            op.source,
            op.target,
            project_path,
        )
    warnings = []
    depth_delta = tgt_depth - src_depth
    if depth_delta != 0:
        warnings.extend(_patch_file_dunder_depth(op.target, depth_delta))
    if old_mod and new_mod and old_mod != new_mod:
        warnings.extend(
            _rewrite_cross_test_imports(
                project_path,
                old_mod,
                [new_mod],
                skip_paths={op.source, op.target},
            )
        )
    return warnings


def _cst_assign_target_names(assign: cst.Assign) -> list[str]:
    return [
        tgt.target.value for tgt in assign.targets if isinstance(tgt.target, cst.Name)
    ]


def _cst_annassign_target_name(ann: cst.AnnAssign) -> str | None:
    return ann.target.value if isinstance(ann.target, cst.Name) else None


def _cst_simple_stmt_names(stmt: cst.SimpleStatementLine) -> list[str]:
    """Names assigned by a top-level ``Assign`` / ``AnnAssign`` line."""
    out: list[str] = []
    for small in stmt.body:
        if isinstance(small, cst.Assign):
            out.extend(_cst_assign_target_names(small))
        elif isinstance(small, cst.AnnAssign):
            name = _cst_annassign_target_name(small)
            if name is not None:
                out.append(name)
    return out


def _cst_stmt_defines_name(stmt: cst.BaseStatement, name: str) -> bool:
    if isinstance(stmt, cst.FunctionDef | cst.ClassDef):
        return stmt.name.value == name
    if not isinstance(stmt, cst.SimpleStatementLine):
        return False
    return name in _cst_simple_stmt_names(stmt)


def _cst_names_in_node(node: cst.CSTNode) -> set[str]:
    out: set[str] = set()

    class _C(cst.CSTVisitor):
        def visit_Name(self, n: cst.Name) -> None:
            out.add(n.value)

    node.visit(_C())
    return out


def _index_top_level_stmts(
    module: cst.Module,
) -> dict[str, cst.BaseStatement]:
    """Map top-level name -> defining statement for a CST module."""
    out: dict[str, cst.BaseStatement] = {}
    for stmt in module.body:
        if isinstance(stmt, cst.FunctionDef | cst.ClassDef):
            out[stmt.name.value] = stmt
        elif isinstance(stmt, cst.SimpleStatementLine):
            for name in _cst_simple_stmt_names(stmt):
                out[name] = stmt
    return out


def _is_copyable_dep_stmt(stmt: cst.BaseStatement) -> bool:
    if isinstance(stmt, cst.SimpleStatementLine):
        return True
    return isinstance(stmt, cst.FunctionDef) and not stmt.name.value.startswith("test_")


def _collect_fixture_closure(
    fx_name: str,
    sib_stmts_by_name: dict[str, cst.BaseStatement],
    anchor_defined: set[str],
) -> set[str]:
    """BFS the names transitively referenced by ``fx_name`` to copy."""
    to_copy: set[str] = {fx_name}
    queue: list[str] = [fx_name]
    visited: set[str] = {fx_name}
    while queue:
        cur_stmt = sib_stmts_by_name.get(queue.pop())
        if cur_stmt is None:
            continue
        for ref in _cst_names_in_node(cur_stmt) - visited:
            visited.add(ref)
            ref_stmt = sib_stmts_by_name.get(ref)
            if ref in anchor_defined or ref_stmt is None:
                continue
            if not _is_copyable_dep_stmt(ref_stmt):
                continue
            to_copy.add(ref)
            queue.append(ref)
    return to_copy


def _ordered_copy_stmts(
    sib_module: cst.Module,
    copy_names: set[str],
) -> list[tuple[str, cst.BaseStatement]]:
    """Walk sibling body in source order and emit (name, stmt) pairs."""
    ordered: list[tuple[str, cst.BaseStatement]] = []
    for stmt in sib_module.body:
        for n in copy_names:
            if _cst_stmt_defines_name(stmt, n):
                ordered.append((n, stmt))
                break
    return ordered


def _format_recovery_msgs(
    fx_name: str,
    anchor_path: Path,
    sibling: Path,
    copied: list[tuple[str, cst.BaseStatement]],
) -> list[str]:
    msgs = [
        f"anchor-fixture-dep-recovered: "
        f"{anchor_path.name}::{n} copied from "
        f"{sibling.name} (used by {fx_name})"
        for n, _ in copied
        if n != fx_name
    ]
    msgs.append(
        f"anchor-fixture-recovered: {anchor_path.name}::"
        f"{fx_name} copied from {sibling.name}"
    )
    return msgs


def _try_recover_from_sibling(
    fx_name: str,
    anchor_path: Path,
    sibling: Path,
    anchor_defined: set[str],
    new_body: list[cst.BaseStatement],
) -> list[str] | None:
    """Attempt to copy ``fx_name`` (+ deps) from ``sibling`` into anchor.

    Returns ``None`` if the sibling doesn't define ``fx_name`` as a
    fixture-eligible function. Otherwise mutates ``anchor_defined`` /
    ``new_body`` in place and returns the list of human-readable msgs.
    """
    if sibling == anchor_path or not sibling.exists():
        return None
    sib_module = _cst_load(sibling)
    if sib_module is None:
        return None
    sib_stmts_by_name = _index_top_level_stmts(sib_module)
    fx_stmt = sib_stmts_by_name.get(fx_name)
    if not isinstance(fx_stmt, cst.FunctionDef):
        return None
    copy_names = _collect_fixture_closure(fx_name, sib_stmts_by_name, anchor_defined)
    copied = _ordered_copy_stmts(sib_module, copy_names)
    for n, stmt in copied:
        new_body.append(stmt)
        anchor_defined.add(n)
    return _format_recovery_msgs(fx_name, anchor_path, sibling, copied)


def _anchor_missing_fixtures(
    anchor_path: Path,
    anchor_fixture_refs: set[str],
) -> tuple[set[str], list[str]] | None:
    """Return (anchor_top_names, sorted_missing) or ``None`` to bail."""
    if not anchor_path.exists() or not anchor_fixture_refs:
        return None
    try:
        anchor_tree = ast.parse(anchor_path.read_text())
    except (OSError, SyntaxError):
        return None
    anchor_top = {
        n.name
        for n in anchor_tree.body
        if isinstance(n, ast.FunctionDef | ast.ClassDef)
    }
    missing = sorted(anchor_fixture_refs - anchor_top)
    if not missing:
        return None
    return anchor_top, missing


def _recover_one_missing_fixture(
    fx_name: str,
    anchor_path: Path,
    post_split_paths: list[Path],
    anchor_defined: set[str],
    new_body: list[cst.BaseStatement],
) -> list[str] | None:
    """Try each sibling until one yields the fixture; ``None`` if none did."""
    for sibling in post_split_paths:
        sib_msgs = _try_recover_from_sibling(
            fx_name, anchor_path, sibling, anchor_defined, new_body
        )
        if sib_msgs is not None:
            return sib_msgs
    return None


def _recover_anchor_fixtures(
    anchor_path: Path,
    anchor_fixture_refs: set[str],
    post_split_paths: list[Path],
) -> list[str]:
    """Copy fixtures referenced by the anchor but missing from its file.

    Background: when ``TestDetectContext`` (the SPLIT anchor) routes to
    its fixtures only via ``pytest.param("X", ...) +
    request.getfixturevalue``, anvil's static analysis sees no usage of
    fixture ``X`` from the anchor and freely moves ``X`` to whichever
    non-anchor target it was also referenced by. After the anvil pass,
    the anchor file lacks the fixture entirely.

    This function reads the anchor's current AST, identifies which
    members of ``anchor_fixture_refs`` are missing top-level, then for
    each missing fixture walks the sibling ``post_split_paths`` and
    copies the first matching ``@pytest.fixture``-decorated definition
    into the anchor (appended at end of file, preserving formatting via
    libcst).
    """
    msgs: list[str] = []
    prep = _anchor_missing_fixtures(anchor_path, anchor_fixture_refs)
    if prep is None:
        return msgs
    anchor_top, missing = prep
    anchor_module = _cst_load(anchor_path)
    if anchor_module is None:
        return msgs
    new_body = list(anchor_module.body)
    anchor_defined = set(anchor_top)
    recovered: set[str] = set()
    for fx_name in missing:
        sib_msgs = _recover_one_missing_fixture(
            fx_name, anchor_path, post_split_paths, anchor_defined, new_body
        )
        if sib_msgs is None:
            continue
        msgs.extend(sib_msgs)
        recovered.add(fx_name)
    if recovered:
        _cst_save(anchor_path, anchor_module.with_changes(body=new_body))
        _backfill_missing_imports(
            anchor_path, anchor_path, anchor_path.parent.parent.parent
        )
    return msgs


def _execute_split(op: FileOp, project_path: Path) -> list[str]:
    """SPLIT a file by routing each *movable unit* to its canonical target.

    A movable unit = a top-level test_* function or a homogeneous Test*
    class. Heterogeneous Test* classes (divergent method tuples) must
    have been flattened first by Stage 0; if any remain, we bail out.

    The largest unit-group stays in source (rename handled by stage 4
    or by this function if the canonical name differs).
    """
    assert move_symbols is not None, "axm-anvil not importable"
    assert isinstance(op.target, list)
    tier_str = _tier_for_path(op.source)
    if tier_str not in ("integration", "e2e"):
        return [f"split skipped: source not under tests/integration|e2e ({op.source})"]
    if not op.source.exists():
        return [f"split skipped: source missing ({op.source})"]
    tree = ast.parse(op.source.read_text())
    pkg_prefixes = get_pkg_prefixes(project_path)
    scripts = _load_project_scripts(project_path)
    single_binary = next(iter(scripts)) if len(scripts) == 1 else None
    leftover = [
        cls.name
        for cls in _top_level_test_classes(tree)
        if _class_needs_flatten(
            cls,
            tree,
            tier=tier_str,
            pkg_prefixes=pkg_prefixes,
            scripts=scripts,
            single_binary=single_binary,
        )
    ]
    if leftover:
        # B1: pathological-AND-heterogeneous classes survive Stage 0.
        # Bail explicitly; collect_unfixable surfaces these.
        return [
            f"split skipped (pathological): {op.source.name} has "
            f"heterogeneous Test* classes that cannot be flattened: "
            f"{leftover}"
        ]
    routes = _per_unit_canonical(op.source, tier_str, project_path)
    if not routes:
        return [f"split skipped: no movable units in {op.source}"]
    if len(routes) < 2:
        return [
            f"split skipped: {op.source.name} has <2 unit-groups "
            "(file is cohesive at canonical-name level)"
        ]
    anchor = max(routes.items(), key=lambda kv: (len(kv[1]), kv[0]))[0]
    warnings: list[str] = []
    original_source = op.source
    original_module = _module_path_for_test_file(original_source, project_path)
    post_split_paths: list[Path] = []

    # Compute fixtures the anchor will still need after non-anchor moves.
    # When a non-anchor unit also references a fixture, marker-fixture
    # follow-up duplicates that fixture into target — but anvil deletes
    # the source-side definition if it's no longer used by remaining
    # source content. The anchor (which stays in source then becomes
    # the target via _git_mv) thus loses its fixtures silently.
    # Solution: pin anchor-referenced fixtures so non-anchor moves see
    # them as "needed by remaining content" and leave them in source.
    def _fixtures_referenced_by(unit_names: set[str]) -> set[str]:
        """Collect all fixture names referenced by units of given names.

        Pulls from three sites: marker fixtures (``usefixtures``),
        string-literal fixtures (``pytest.param`` + ``getfixturevalue``)
        and direct params on the test signature (or class methods).
        """
        refs: set[str] = set()
        for n in tree.body:
            if not (
                isinstance(n, ast.FunctionDef | ast.ClassDef) and n.name in unit_names
            ):
                continue
            refs |= _string_literal_fixtures_in_unit(n)
            refs |= _marker_fixtures_in_unit(n)
            if isinstance(n, ast.ClassDef):
                for m in n.body:
                    if isinstance(m, ast.FunctionDef):
                        refs |= {a.arg for a in m.args.args}
            else:
                refs |= {a.arg for a in n.args.args}
        return refs

    anchor_fixture_refs = _fixtures_referenced_by(set(routes[anchor]))
    # Track fixtures still needed by units not yet moved. Each iteration
    # drops the current target's needs, so the pin set shrinks as we
    # progress. Without this, anvil's marker-fixture follow-up copies a
    # fixture into the FIRST non-anchor target, then deletes it from
    # source (no source-side reference remains), leaving subsequent
    # non-anchor targets without the fixture — even though they declare
    # the same ``usefixtures`` marker.
    non_anchor_units: dict[str, set[str]] = {
        canonical: set(unit_names)
        for canonical, unit_names in routes.items()
        if canonical != anchor
    }
    for canonical, unit_names in routes.items():
        if canonical == anchor:
            continue
        target = op.source.parent / canonical
        if not target.exists():
            target.write_text(f'"""Split from ``{op.source.name}``."""\n')
        non_anchor_units.pop(canonical, None)
        pending_refs: set[str] = set()
        for pending_names in non_anchor_units.values():
            pending_refs |= _fixtures_referenced_by(pending_names)
        sub_warnings, _ = _safe_move_units(
            op.source,
            target,
            unit_names,
            project_path,
            keep_in_source=anchor_fixture_refs | pending_refs,
        )
        warnings.extend(sub_warnings)
        post_split_paths.append(target)
    anchor_path: Path | None = None
    if op.source.exists() and op.source.name != anchor:
        target = op.source.parent / anchor
        if target.exists() and target != op.source:
            tree = ast.parse(op.source.read_text())
            residual_units = _movable_units_at_top_level(tree)
            if residual_units:
                sub_warnings, _ = _safe_move_units(
                    op.source, target, residual_units, project_path
                )
                warnings.extend(sub_warnings)
            _delete_source_if_empty_tests(op.source)
        else:
            _git_mv(op.source, target)
        post_split_paths.append(target)
        anchor_path = target
    elif op.source.exists():
        post_split_paths.append(op.source)
        anchor_path = op.source
    # Post-split fixture recovery: when the anchor references a fixture
    # by string-literal (pytest.param("X", ...) + request.getfixturevalue),
    # anvil's earlier moves saw no direct usage and removed the def from
    # source. The anchor (now its own file) is left referencing missing
    # names. Find each missing fixture in the sibling post-split paths
    # and copy its definition back into the anchor.
    if anchor_path is not None and anchor_fixture_refs:
        warnings.extend(
            _recover_anchor_fixtures(
                anchor_path,
                anchor_fixture_refs,
                post_split_paths,
            )
        )
    if original_module:
        new_modules = []
        seen: set[str] = set()
        for p in post_split_paths:
            mod = _module_path_for_test_file(p, project_path)
            if mod and mod != original_module and mod not in seen:
                new_modules.append(mod)
                seen.add(mod)
        if new_modules:
            warnings.extend(
                _rewrite_cross_test_imports(
                    project_path,
                    original_module,
                    new_modules,
                    skip_paths={original_source, *post_split_paths},
                )
            )
    return warnings


def _execute_merge(op: FileOp, project_path: Path) -> list[str]:
    """MERGE source's units into target via _safe_move_units."""
    assert isinstance(op.target, Path)
    if not op.source.exists() or not op.target.exists():
        return [f"merge skipped: missing ({op.source} -> {op.target})"]
    source_tree = ast.parse(op.source.read_text())
    source_units = _movable_units_at_top_level(source_tree)
    if not source_units:
        return [f"merge skipped: {op.source} has no top-level movable units"]
    old_mod = _module_path_for_test_file(op.source, project_path)
    new_mod = _module_path_for_test_file(op.target, project_path)
    warnings, _ = _safe_move_units(op.source, op.target, source_units, project_path)
    _delete_source_if_empty_tests(op.source)
    if old_mod and new_mod and old_mod != new_mod and not op.source.exists():
        warnings.extend(
            _rewrite_cross_test_imports(
                project_path,
                old_mod,
                [new_mod],
                skip_paths={op.source, op.target},
            )
        )
    return warnings


def execute(ops: list[FileOp], project_path: Path) -> list[str]:
    """Apply ops in order. Returns aggregated warnings."""
    warnings: list[str] = []
    for op in ops:
        if op.kind == "flatten":
            warnings.extend(_execute_flatten(op, project_path))
        elif op.kind == "relocate":
            warnings.extend(_execute_relocate(op, project_path))
        elif op.kind == "rename":
            warnings.extend(_execute_rename(op, project_path))
        elif op.kind == "split":
            warnings.extend(_execute_split(op, project_path))
        elif op.kind == "merge":
            warnings.extend(_execute_merge(op, project_path))
    return warnings
