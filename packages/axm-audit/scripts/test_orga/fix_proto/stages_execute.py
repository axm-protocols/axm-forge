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
    "execute",
    "_execute_flatten",
    "_execute_relocate",
    "_execute_rename",
    "_execute_split",
    "_execute_merge",
    "_reroute_through_safe_move",
]


def _execute_flatten(op: FileOp, project_path: Path) -> list[str]:
    """Flatten the listed Test* classes in op.source.

    Skips pathological cases (op.split_map is None — signaled by planner).
    """
    if op.split_map is None:
        return [
            f"flatten skipped: {op.rationale} ({op.source.name})"
        ]
    if not op.source.exists():
        return [f"flatten skipped: {op.source} missing"]
    text = op.source.read_text()
    for class_name in op.split_map.keys():
        text = _flatten_class_to_top_level(text, class_name)
    op.source.write_text(text)
    _reorder_module_statements(op.source)
    return [
        f"flatten: rewrote {op.source.name} ({list(op.split_map.keys())})"
    ]


def _reroute_through_safe_move(
    kind: str, source: Path, target: Path, project_path: Path,
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
        sub_warnings, _ = _safe_move_units(
            source, target, units, project_path
        )
        warnings.extend(sub_warnings)
    _delete_source_if_empty_tests(source)
    if old_mod and new_mod and old_mod != new_mod and not source.exists():
        warnings.extend(_rewrite_cross_test_imports(
            project_path, old_mod, [new_mod],
            skip_paths={source, target},
        ))
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
            "relocate", op.source, op.target, project_path,
        )
    old_mod = _module_path_for_test_file(op.source, project_path)
    new_mod = _module_path_for_test_file(op.target, project_path)
    src_depth = _file_depth_from_project(op.source, project_path)
    tgt_depth = _file_depth_from_project(op.target, project_path)
    try:
        _git_mv(op.source, op.target)
    except FileExistsError:
        return _reroute_through_safe_move(
            "relocate", op.source, op.target, project_path,
        )
    warnings = []
    depth_delta = tgt_depth - src_depth
    if depth_delta != 0:
        warnings.extend(_patch_file_dunder_depth(op.target, depth_delta))
    if old_mod and new_mod and old_mod != new_mod:
        warnings.extend(_rewrite_cross_test_imports(
            project_path, old_mod, [new_mod],
            skip_paths={op.source, op.target},
        ))
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
            "rename", op.source, op.target, project_path,
        )
    old_mod = _module_path_for_test_file(op.source, project_path)
    new_mod = _module_path_for_test_file(op.target, project_path)
    src_depth = _file_depth_from_project(op.source, project_path)
    tgt_depth = _file_depth_from_project(op.target, project_path)
    try:
        _git_mv(op.source, op.target)
    except FileExistsError:
        return _reroute_through_safe_move(
            "rename", op.source, op.target, project_path,
        )
    warnings = []
    depth_delta = tgt_depth - src_depth
    if depth_delta != 0:
        warnings.extend(_patch_file_dunder_depth(op.target, depth_delta))
    if old_mod and new_mod and old_mod != new_mod:
        warnings.extend(_rewrite_cross_test_imports(
            project_path, old_mod, [new_mod],
            skip_paths={op.source, op.target},
        ))
    return warnings


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
    if not anchor_path.exists() or not anchor_fixture_refs:
        return msgs
    try:
        anchor_tree = ast.parse(anchor_path.read_text())
    except (OSError, SyntaxError):
        return msgs
    anchor_top = {
        n.name for n in anchor_tree.body
        if isinstance(n, ast.FunctionDef | ast.ClassDef)
    }
    missing = sorted(anchor_fixture_refs - anchor_top)
    if not missing:
        return msgs
    anchor_module = _cst_load(anchor_path)
    if anchor_module is None:
        return msgs
    new_body = list(anchor_module.body)
    anchor_defined = set(anchor_top)
    recovered: set[str] = set()

    def _stmt_defines_name(stmt: cst.BaseStatement, name: str) -> bool:
        if isinstance(stmt, cst.FunctionDef | cst.ClassDef):
            return stmt.name.value == name
        if isinstance(stmt, cst.SimpleStatementLine):
            for small in stmt.body:
                if isinstance(small, cst.Assign):
                    for tgt in small.targets:
                        if (
                            isinstance(tgt.target, cst.Name)
                            and tgt.target.value == name
                        ):
                            return True
                elif isinstance(small, cst.AnnAssign):
                    if (
                        isinstance(small.target, cst.Name)
                        and small.target.value == name
                    ):
                        return True
        return False

    def _names_in_node(node: cst.CSTNode) -> set[str]:
        out: set[str] = set()
        class _C(cst.CSTVisitor):
            def visit_Name(self, n: cst.Name) -> None:
                out.add(n.value)
        node.visit(_C())
        return out

    for fx_name in missing:
        for sibling in post_split_paths:
            if sibling == anchor_path or not sibling.exists():
                continue
            sib_module = _cst_load(sibling)
            if sib_module is None:
                continue
            sib_stmts_by_name: dict[str, cst.BaseStatement] = {}
            for stmt in sib_module.body:
                if isinstance(stmt, cst.FunctionDef | cst.ClassDef):
                    sib_stmts_by_name[stmt.name.value] = stmt
                elif isinstance(stmt, cst.SimpleStatementLine):
                    for small in stmt.body:
                        if isinstance(small, cst.Assign):
                            for tgt in small.targets:
                                if isinstance(tgt.target, cst.Name):
                                    sib_stmts_by_name[tgt.target.value] = stmt
                        elif isinstance(small, cst.AnnAssign):
                            if isinstance(small.target, cst.Name):
                                sib_stmts_by_name[small.target.value] = stmt
            fx_stmt = sib_stmts_by_name.get(fx_name)
            if fx_stmt is None or not isinstance(fx_stmt, cst.FunctionDef):
                continue
            # Closure: recover the fixture + any top-level name it
            # references that isn't already defined in the anchor.
            to_copy: list[tuple[str, cst.BaseStatement]] = [(fx_name, fx_stmt)]
            queue: list[str] = [fx_name]
            visited: set[str] = {fx_name}
            while queue:
                cur = queue.pop()
                cur_stmt = sib_stmts_by_name.get(cur)
                if cur_stmt is None:
                    continue
                for ref in _names_in_node(cur_stmt):
                    if ref in visited:
                        continue
                    visited.add(ref)
                    if ref in anchor_defined:
                        continue
                    if ref in sib_stmts_by_name:
                        ref_stmt = sib_stmts_by_name[ref]
                        # Only copy module-level constants (UPPER_SNAKE_CASE
                        # or similar) and helper functions — never copy
                        # other tests/classes (would duplicate test runs).
                        if (
                            isinstance(ref_stmt, cst.SimpleStatementLine)
                            or (
                                isinstance(ref_stmt, cst.FunctionDef)
                                and not ref_stmt.name.value.startswith("test_")
                            )
                        ):
                            to_copy.append((ref, ref_stmt))
                            queue.append(ref)
            # Append in source order: walk sib_module.body and pick the
            # to-copy stmts so dependencies precede dependents.
            copy_names = {n for n, _ in to_copy}
            ordered_copy: list[cst.BaseStatement] = []
            for stmt in sib_module.body:
                for n in copy_names:
                    if _stmt_defines_name(stmt, n):
                        ordered_copy.append(stmt)
                        anchor_defined.add(n)
                        if n != fx_name:
                            msgs.append(
                                f"anchor-fixture-dep-recovered: "
                                f"{anchor_path.name}::{n} copied from "
                                f"{sibling.name} (used by {fx_name})"
                            )
                        break
            new_body.extend(ordered_copy)
            recovered.add(fx_name)
            msgs.append(
                f"anchor-fixture-recovered: {anchor_path.name}::"
                f"{fx_name} copied from {sibling.name}"
            )
            break
    if recovered:
        _cst_save(anchor_path, anchor_module.with_changes(body=new_body))
        _backfill_missing_imports(anchor_path, anchor_path, anchor_path.parent.parent.parent)
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
        return [
            f"split skipped: source not under tests/integration|e2e "
            f"({op.source})"
        ]
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
            cls, tree, tier=tier_str, pkg_prefixes=pkg_prefixes,
            scripts=scripts, single_binary=single_binary,
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
    anchor_unit_names = set(routes[anchor])
    anchor_nodes = [
        n for n in tree.body
        if isinstance(n, ast.FunctionDef | ast.ClassDef)
        and n.name in anchor_unit_names
    ]
    anchor_fixture_refs: set[str] = set()
    for node in anchor_nodes:
        anchor_fixture_refs |= _string_literal_fixtures_in_unit(node)
        anchor_fixture_refs |= _marker_fixtures_in_unit(node)
        # Also pick up fixtures used as direct params (no markers).
        if isinstance(node, ast.ClassDef):
            for m in node.body:
                if isinstance(m, ast.FunctionDef):
                    anchor_fixture_refs |= {a.arg for a in m.args.args}
        else:
            anchor_fixture_refs |= {a.arg for a in node.args.args}
    for canonical, unit_names in routes.items():
        if canonical == anchor:
            continue
        target = op.source.parent / canonical
        if not target.exists():
            target.write_text(f'"""Split from ``{op.source.name}``."""\n')
        sub_warnings, _ = _safe_move_units(
            op.source, target, unit_names, project_path,
            keep_in_source=anchor_fixture_refs,
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
        warnings.extend(_recover_anchor_fixtures(
            anchor_path, anchor_fixture_refs, post_split_paths,
        ))
    if original_module:
        new_modules = []
        seen: set[str] = set()
        for p in post_split_paths:
            mod = _module_path_for_test_file(p, project_path)
            if mod and mod != original_module and mod not in seen:
                new_modules.append(mod)
                seen.add(mod)
        if new_modules:
            warnings.extend(_rewrite_cross_test_imports(
                project_path, original_module, new_modules,
                skip_paths={original_source, *post_split_paths},
            ))
    return warnings


def _execute_merge(op: FileOp, project_path: Path) -> list[str]:
    """MERGE source's units into target via _safe_move_units."""
    assert isinstance(op.target, Path)
    if not op.source.exists() or not op.target.exists():
        return [f"merge skipped: missing ({op.source} -> {op.target})"]
    source_tree = ast.parse(op.source.read_text())
    source_units = _movable_units_at_top_level(source_tree)
    if not source_units:
        return [
            f"merge skipped: {op.source} has no top-level movable units"
        ]
    old_mod = _module_path_for_test_file(op.source, project_path)
    new_mod = _module_path_for_test_file(op.target, project_path)
    warnings, _ = _safe_move_units(
        op.source, op.target, source_units, project_path
    )
    _delete_source_if_empty_tests(op.source)
    if old_mod and new_mod and old_mod != new_mod and not op.source.exists():
        warnings.extend(_rewrite_cross_test_imports(
            project_path, old_mod, [new_mod],
            skip_paths={op.source, op.target},
        ))
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
