"""Tier-layout reshape + safe move wrapper.

Splits into four concerns:

* ``relocate_non_canonical_tiers`` — Stage 0.5 (B4 fix): move
  ``tests/functional/`` and any other non-canonical tier subdir into
  ``tests/integration/`` so the rest of the pipeline only ever sees
  canonical tiers (unit / integration / e2e).
* ``flatten_tier_layout`` + ``_flatten_single_tier`` + ``_prune_empty_test_subdirs``
  — Stage 1.5: collapse nested ``tests/integration/<subdir>/`` to flat
  layout the AXM convention requires.
* ``_rewrite_cross_test_imports`` — when a file moves and changes its
  dotted module path, rewrite every ``from <old_module> import ...``
  in the project so importers don't break.
* ``_safe_move_units`` + ``_resolve_helper_conflicts`` +
  ``_resolve_conftest_shadowing`` — wrap axm-anvil's ``move_symbols``
  with collision detection, helper-body conflict resolution, and
  conftest shadowing guards. The bulk of the proto's "magic" lives here.
"""

from __future__ import annotations

import ast
import hashlib
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

try:
    from axm_anvil.core.move import move_symbols
except ImportError:  # pragma: no cover
    move_symbols = None  # type: ignore[assignment]

from .cst_rewrite import (
    _backfill_missing_imports,
    _delete_function_from_source,
    _patch_file_dunder_depth,
    _rename_name_in_module,
    _rename_top_level_in_source,
    _reorder_module_statements,
)
from .io_primitives import _git_mv
from .models import CANONICAL_TIERS
from .paths import file_depth_from_project, module_path_for_test_file
from .tests_ast import (
    _collect_conftest_fixtures,
    _collect_marker_fixtures_to_move,
    _collect_module_level_deps_to_copy,
    _names_referenced_in_unit,
    _source_top_level_definitions,
    _stmt_assignment_targets,
    _string_literal_fixtures_in_unit,
    func_body_hash,
    marker_fixtures_in_unit,
    top_level_helpers,
)

__all__ = [
    "_flatten_single_tier",
    "_prune_empty_test_subdirs",
    "_resolve_conftest_shadowing",
    "_resolve_helper_conflicts",
    "_rewrite_cross_test_imports",
    "_safe_move_units",
    "flatten_tier_layout",
    "relocate_non_canonical_tiers",
]


# ---------------------------------------------------------------------------
# Stage 0.5 — relocate non-canonical tier dirs
# ---------------------------------------------------------------------------


_NON_TEST_DIR_NAMES: frozenset[str] = frozenset({"fixtures"})
"""Non-canonical ``tests/`` children that hold non-test data.

By AXM convention ``tests/fixtures/`` holds static test data (corpora,
snapshots, baselines) consumed by real tests; pytest excludes it from
collection via ``collect_ignore_glob``, and the layout pipeline must do
the same so corpus files don't get relocated to ``tests/integration/``.
"""


def _iter_non_canonical_tier_dirs(tests_root: Path) -> list[Path]:
    """Yield direct children of ``tests_root`` that are non-canonical tiers.

    Skips canonical tiers (``unit/``, ``integration/``, ``e2e/``), hidden
    or ``_``-prefixed dirs, and ``tests/fixtures/`` (see
    ``_NON_TEST_DIR_NAMES``).
    """
    out: list[Path] = []
    for child in sorted(tests_root.iterdir()):
        if not child.is_dir() or child.name in CANONICAL_TIERS:
            continue
        if child.name.startswith(("_", ".")):
            continue
        if child.name in _NON_TEST_DIR_NAMES:
            continue
        out.append(child)
    return out


def _unique_integration_target(src: Path, integration: Path) -> Path:
    target = integration / src.name
    counter = 2
    while target.exists() and target != src:
        target = integration / f"{src.stem}_{counter}.py"
        counter += 1
    return target


def _relocate_single_file(src: Path, target: Path, project_path: Path) -> list[str]:
    msgs: list[str] = []
    old_mod = module_path_for_test_file(src, project_path)
    depth_delta = file_depth_from_project(
        target, project_path
    ) - file_depth_from_project(src, project_path)
    _git_mv(src, target)
    if depth_delta != 0:
        msgs.extend(_patch_file_dunder_depth(target, depth_delta))
    new_mod = module_path_for_test_file(target, project_path)
    if old_mod and new_mod and old_mod != new_mod:
        msgs.extend(
            _rewrite_cross_test_imports(
                project_path,
                old_mod,
                [new_mod],
                skip_paths={src, target},
            )
        )
    msgs.append(
        f"non-canonical-tier moved {src.relative_to(project_path)} -> "
        f"{target.relative_to(project_path)}"
    )
    return msgs


def _ensure_integration_pkg(integration: Path, source_child: Path) -> None:
    integration.mkdir(exist_ok=True)
    init_pkg = integration / "__init__.py"
    if not init_pkg.exists() and (source_child / "__init__.py").exists():
        init_pkg.write_text("")


def relocate_non_canonical_tiers(project_path: Path) -> list[str]:
    """Move ``tests/<non_canonical>/test_*.py`` into ``tests/integration/``.

    Tiers ``unit/``, ``integration/``, ``e2e/`` are the only canonical
    pyramid directories (per CLAUDE.md). Files living under any other
    direct child of ``tests/`` — e.g. ``tests/functional/``,
    ``tests/hooks/``, ``tests/tools/`` — cannot be processed by SPLIT /
    MERGE / RENAME because ``tier_for_path`` returns ``None`` for them.

    Default destination is ``tests/integration/`` (the tier for real I/O
    + first-party import), which is the most common landing for legacy
    ``functional/`` tests. Stage 1 RELOCATE will subsequently re-tier
    each file to its correct level based on PYRAMID_LEVEL findings.

    Runs BEFORE Stage 1 so RELOCATE sees only canonical-tier paths.
    """
    msgs: list[str] = []
    tests_root = project_path / "tests"
    if not tests_root.is_dir():
        return msgs
    integration = tests_root / "integration"
    for child in _iter_non_canonical_tier_dirs(tests_root):
        nested_tests = sorted(p for p in child.rglob("test_*.py") if p.is_file())
        if not nested_tests:
            continue
        _ensure_integration_pkg(integration, child)
        for src in nested_tests:
            target = _unique_integration_target(src, integration)
            msgs.extend(_relocate_single_file(src, target, project_path))
        _prune_empty_test_subdirs(child)
        if child.exists() and not any(child.iterdir()):
            child.rmdir()
    return msgs


# ---------------------------------------------------------------------------
# Stage 1.5 — flatten tier subdirectories
# ---------------------------------------------------------------------------


def flatten_tier_layout(project_path: Path) -> list[str]:
    """Flatten ``tests/integration/`` and ``tests/e2e/`` subdirectories.

    The AXM convention (CLAUDE.md) requires integration and e2e tests
    to live *directly* under their tier directory — no nested
    ``tests/integration/hooks/test_x.py``. This stage moves every
    nested ``test_*.py`` up to the tier root, renames on collision
    by prefixing the subdirectory name (``hooks/test_x.py`` →
    ``test_hooks_x.py``), rewrites importers via
    ``_rewrite_cross_test_imports``, and removes the now-empty
    subdirectories (preserving ``__init__.py`` / ``conftest.py`` by
    skipping the prune if those remain).

    Runs AFTER Stage 1 (RELOCATE) so it acts on the final tier
    classification, and BEFORE Stages 2-4 (SPLIT/MERGE/RENAME) which
    assume a flat layout.

    Unit tests intentionally MIRROR the source layout — nested
    subdirectories are correct there, so this stage skips ``tests/unit``.
    """
    msgs: list[str] = []
    tests_root = project_path / "tests"
    if not tests_root.is_dir():
        return msgs
    for tier in ("integration", "e2e"):
        tier_dir = tests_root / tier
        if not tier_dir.is_dir():
            continue
        msgs.extend(_flatten_single_tier(project_path, tier_dir))
    return msgs


def _resolve_flatten_target(src: Path, tier_dir: Path) -> Path:
    target = tier_dir / src.name
    if not target.exists() or target == src:
        return target
    prefix = "_".join(src.relative_to(tier_dir).parts[:-1])
    stem = src.stem.removeprefix("test_")
    target = tier_dir / f"test_{prefix}_{stem}.py"
    counter = 2
    while target.exists():
        target = tier_dir / f"test_{prefix}_{stem}_{counter}.py"
        counter += 1
    return target


def _flatten_one_file(project_path: Path, tier_dir: Path, src: Path) -> list[str]:
    msgs: list[str] = []
    target = _resolve_flatten_target(src, tier_dir)
    old_mod = module_path_for_test_file(src, project_path)
    depth_delta = file_depth_from_project(
        target, project_path
    ) - file_depth_from_project(src, project_path)
    _git_mv(src, target)
    if depth_delta != 0:
        msgs.extend(_patch_file_dunder_depth(target, depth_delta))
    new_mod = module_path_for_test_file(target, project_path)
    if old_mod and new_mod and old_mod != new_mod:
        msgs.extend(
            _rewrite_cross_test_imports(
                project_path,
                old_mod,
                [new_mod],
                skip_paths={src, target},
            )
        )
    msgs.append(
        f"flattened {src.relative_to(project_path)} -> "
        f"{target.relative_to(project_path)}"
    )
    return msgs


def _flatten_single_tier(project_path: Path, tier_dir: Path) -> list[str]:
    """Move every nested ``test_*.py`` under *tier_dir* up to *tier_dir* root."""
    nested = sorted(
        p for p in tier_dir.rglob("test_*.py") if p.is_file() and p.parent != tier_dir
    )
    if not nested:
        return []
    msgs: list[str] = []
    for src in nested:
        msgs.extend(_flatten_one_file(project_path, tier_dir, src))
    _prune_empty_test_subdirs(tier_dir)
    return msgs


def _subdir_has_test_file(sub: Path) -> bool:
    return any(
        f.is_file() and f.name.startswith("test_") and f.suffix == ".py"
        for f in sub.iterdir()
    )


def _remove_subdir_files(sub: Path) -> None:
    for f in sub.iterdir():
        if not f.is_file():
            continue
        rc = subprocess.run(
            ["git", "rm", "-q", str(f)],
            capture_output=True,
            text=True,
        )
        if rc.returncode != 0:
            f.unlink()


def _prune_empty_test_subdirs(tier_dir: Path) -> None:
    """Remove subdirectories under *tier_dir* that contain no ``test_*.py``.

    Walks bottom-up so empty parents become eligible after their
    children are removed. Always keeps the tier directory itself.
    ``__init__.py`` / ``conftest.py`` alone don't keep a subdir
    alive — they're scaffolding for tests that have moved out.
    """
    subdirs = sorted(
        (p for p in tier_dir.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    )
    for sub in subdirs:
        if sub == tier_dir or _subdir_has_test_file(sub):
            continue
        _remove_subdir_files(sub)
        try:
            sub.rmdir()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Cross-test import rewriter (used after every move)
# ---------------------------------------------------------------------------


def _names_segment(node: ast.ImportFrom) -> str:
    return ", ".join(
        a.name if a.asname is None else f"{a.name} as {a.asname}" for a in node.names
    )


def _trailing_comment(text_lines: list[str], lineno: int) -> str:
    idx = lineno - 1
    if not (0 <= idx < len(text_lines)):
        return ""
    hash_idx = text_lines[idx].find("#")
    if hash_idx == -1:
        return ""
    return "  " + text_lines[idx][hash_idx:].rstrip()


def _collect_import_edits(
    tree: ast.AST,
    text_lines: list[str],
    old_module: str,
    new_modules: list[str],
) -> list[tuple[ast.ImportFrom, str]]:
    edits: list[tuple[ast.ImportFrom, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level != 0 or node.module != old_module:
            continue
        names_segment = _names_segment(node)
        trailing = _trailing_comment(text_lines, node.lineno)
        replacement = "\n".join(
            f"from {mod} import {names_segment}{trailing}" for mod in new_modules
        )
        edits.append((node, replacement))
    return edits


def _apply_import_edits(text: str, edits: list[tuple[ast.ImportFrom, str]]) -> str:
    lines = text.splitlines(keepends=True)
    for node, replacement in sorted(edits, key=lambda e: e[0].lineno, reverse=True):
        start = node.lineno - 1
        end = node.end_lineno or node.lineno
        tail = "\n" if lines[end - 1].endswith("\n") else ""
        lines[start:end] = [replacement + tail]
    return "".join(lines)


def _rewrite_file_imports(py: Path, old_module: str, new_modules: list[str]) -> bool:
    try:
        text = py.read_text()
    except OSError:
        return False
    if old_module not in text:
        return False
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False
    edits = _collect_import_edits(tree, text.splitlines(), old_module, new_modules)
    if not edits:
        return False
    py.write_text(_apply_import_edits(text, edits))
    return True


def _rewrite_cross_test_imports(
    project_path: Path,
    old_module: str,
    new_modules: list[str],
    skip_paths: set[Path],
) -> list[str]:
    """Rewrite ``from <old_module> import ...`` across the project.

    When a SPLIT/MERGE/RENAME changes which file owns the symbols
    previously imported via ``from tests.<old_stem> import <names>``,
    the importing test files must be rewritten or pytest collection
    breaks (real bug observed on axm-init: ``test_workspace_checks`` was
    split into N files but ``tests/unit/checks/test_workspace.py``
    still tried to import the now-missing module).

    Args:
        old_module: dotted module the importer used to reference.
        new_modules: replacement modules. For RENAME/MERGE this is a
            single-element list. For SPLIT this is the post-split list
            of canonical module paths.
        skip_paths: paths to skip (typically op.source, op.target).

    Returns: list of human-readable rewrite messages.
    """
    if not new_modules:
        return []
    skip_resolved = {p.resolve() for p in skip_paths}
    msgs: list[str] = []
    for py in project_path.rglob("*.py"):
        if py.resolve() in skip_resolved:
            continue
        if not _rewrite_file_imports(py, old_module, new_modules):
            continue
        msgs.append(
            f"rewrote import in {py.relative_to(project_path)}: "
            f"{old_module} -> {new_modules}"
        )
    return msgs


# ---------------------------------------------------------------------------
# Helper-body conflict + conftest shadow resolution (called by safe_move_units)
# ---------------------------------------------------------------------------


def _resolve_helper_conflicts(
    source_tree: ast.Module,
    target_tree: ast.Module,
    moving_unit_names: list[str],
    source_stem: str,
    target: Path | None = None,
    project_path: Path | None = None,
) -> dict[str, str]:
    """Build a rename map for helpers whose body differs between source & target.

    For every top-level helper ``H`` referenced by a moving unit:

      * If ``H`` is in source AND in target with a different body hash
        (Bug 1/3 case), rename ``H`` in source to ``H__from_<stem>``.
        Anvil's ``shared_helpers="duplicate"`` then copies the renamed
        helper to target without collision.

      * If ``H`` is in source but NOT in target AND a conftest on
        target's ancestor chain provides a fixture named ``H``
        (Bug 4 residual: ``rich_pkg``), rename in source too. Reason:
        anvil would duplicate source's ``H`` into target, shadowing
        conftest — breaking any test in target (whether pre-existing
        or moved later) that relies on conftest's body. Renaming
        source's ``H`` keeps both worlds working: moved tests bind to
        the renamed helper (their original body), target's other
        tests bind to conftest.

    Helpers that are identical in source and target (same body_hash)
    don't need renaming — anvil's duplicate logic correctly skips the
    copy. Helpers only in source with no conftest shadow get
    duplicated as-is.
    """
    source_helpers = top_level_helpers(source_tree)
    target_helpers = top_level_helpers(target_tree)
    source_top_nodes = _index_top_level_defs(source_tree)
    moving_names = set(moving_unit_names)
    moving_nodes = [n for n in source_top_nodes.values() if n.name in moving_names]
    referenced: set[str] = set()
    for node in moving_nodes:
        referenced |= _all_references_in_unit(node)
    _extend_transitive_references(referenced, source_top_nodes)
    conftest_fixtures: set[str] = set()
    if target is not None and project_path is not None:
        conftest_fixtures = _collect_conftest_fixtures(target, project_path)
    suffix = f"__from_{source_stem}"
    rename: dict[str, str] = {}
    for name in sorted(referenced):
        new_name = name + suffix
        if _should_rename_helper(
            name, new_name, source_helpers, target_helpers, conftest_fixtures
        ):
            rename[name] = new_name
    return rename


def _index_top_level_defs(
    tree: ast.Module,
) -> dict[str, ast.FunctionDef | ast.ClassDef]:
    return {
        n.name: n  # type: ignore[misc]
        for n in tree.body
        if isinstance(n, ast.FunctionDef | ast.ClassDef)
    }


def _all_references_in_unit(node: ast.stmt) -> set[str]:
    return (
        _names_referenced_in_unit(node)
        | marker_fixtures_in_unit(node)
        | _string_literal_fixtures_in_unit(node)
    )


def _extend_transitive_references(
    referenced: set[str],
    source_top_nodes: dict[str, ast.FunctionDef | ast.ClassDef],
) -> None:
    """Iterate until the reference closure over source helpers stabilises."""
    frontier = set(referenced)
    while frontier:
        next_frontier: set[str] = set()
        for name in frontier:
            helper = source_top_nodes.get(name)
            if helper is None:
                continue
            new_refs = _all_references_in_unit(helper) - referenced
            referenced |= new_refs
            next_frontier |= new_refs
        frontier = next_frontier


def _should_rename_helper(
    name: str,
    new_name: str,
    source_helpers: dict[str, tuple[str, ast.stmt]],
    target_helpers: dict[str, tuple[str, ast.stmt]],
    conftest_fixtures: set[str],
) -> bool:
    if name not in source_helpers:
        return False
    if name in target_helpers:
        if source_helpers[name][0] == target_helpers[name][0]:
            return False
    elif name not in conftest_fixtures:
        return False
    return new_name not in source_helpers and new_name not in target_helpers


def _resolve_conftest_shadowing(
    source_tree: ast.Module,
    target_tree: ast.Module,
    moving_unit_names: list[str],
    target: Path,
    project_path: Path,
    target_stem: str,
) -> dict[str, str]:
    """Build a rename map for target-local helpers that shadow conftest.

    Resolves Bug 4 residual (``rich_pkg`` in ``test_inspect_tool.py``).
    When a moved test references ``H`` (via parameter injection or
    ``@pytest.mark.usefixtures("H")``) AND:

      * source has no top-level ``H`` definition → source's tests
        relied on conftest's ``H``;
      * target has a top-level ``H`` definition → it would shadow
        conftest, binding the moved tests to the wrong body;
      * a conftest on target's ancestor chain provides ``H``.

    Then we rename target's local ``H`` to ``H__local_<target_stem>``
    (def + every reference inside target's existing tests). Target's
    own tests keep working with the renamed local; the soon-to-be-moved
    tests reference ``H`` and pytest resolves to conftest's version.
    """
    referenced = _referenced_names_in_moving_units(source_tree, moving_unit_names)
    if not referenced:
        return {}
    source_helpers = top_level_helpers(source_tree)
    target_helpers = top_level_helpers(target_tree)
    conftest_fixtures = _collect_conftest_fixtures(target, project_path)
    suffix = f"__local_{target_stem}"
    return _build_shadow_rename_map(
        referenced, source_helpers, target_helpers, conftest_fixtures, suffix
    )


def _referenced_names_in_moving_units(
    source_tree: ast.Module, moving_unit_names: list[str]
) -> set[str]:
    moving = set(moving_unit_names)
    moving_nodes = [
        n
        for n in source_tree.body
        if isinstance(n, ast.FunctionDef | ast.ClassDef) and n.name in moving
    ]
    referenced: set[str] = set()
    for node in moving_nodes:
        referenced |= _names_referenced_in_unit(node)
        referenced |= marker_fixtures_in_unit(node)
        referenced |= _string_literal_fixtures_in_unit(node)
    return referenced


def _build_shadow_rename_map(
    referenced: set[str],
    source_helpers: dict[str, tuple[str, ast.stmt]],
    target_helpers: dict[str, tuple[str, ast.stmt]],
    conftest_fixtures: set[str],
    suffix: str,
) -> dict[str, str]:
    rename: dict[str, str] = {}
    for name in sorted(referenced):
        if name in source_helpers or name not in target_helpers:
            continue
        if name not in conftest_fixtures:
            continue
        new_name = name + suffix
        if new_name in target_helpers:
            continue
        rename[name] = new_name
    return rename


# ---------------------------------------------------------------------------
# Safe move — wraps anvil with collision resolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _MoveIndex:
    source_tree: ast.Module
    target_tree: ast.Module
    target_top_names: set[str]
    source_funcs: dict[str, ast.FunctionDef]
    target_funcs: dict[str, ast.FunctionDef]
    source_class_names: set[str]
    stem: str
    fn_suffix: str
    cls_suffix: str


def _top_def_names(tree: ast.Module) -> set[str]:
    return {n.name for n in tree.body if isinstance(n, ast.FunctionDef | ast.ClassDef)}


def _top_test_funcs(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    return {
        n.name: n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    }


def _top_class_names(tree: ast.Module) -> set[str]:
    return {n.name for n in tree.body if isinstance(n, ast.ClassDef)}


def _camel_from_snake(stem: str) -> str:
    return "From" + "".join(p.capitalize() for p in stem.split("_") if p)


def _build_move_index(source: Path, target: Path) -> _MoveIndex:
    source_tree = ast.parse(source.read_text())
    target_tree = ast.parse(target.read_text())
    stem = source.stem.removeprefix("test_")
    return _MoveIndex(
        source_tree=source_tree,
        target_tree=target_tree,
        target_top_names=_top_def_names(target_tree),
        source_funcs=_top_test_funcs(source_tree),
        target_funcs=_top_test_funcs(target_tree),
        source_class_names=_top_class_names(source_tree),
        stem=stem,
        fn_suffix=f"__from_{stem}",
        cls_suffix=_camel_from_snake(stem),
    )


def _bounded_rename(name: str, suffix: str, stem: str) -> str:
    full = name + suffix
    max_id_len = 73
    if len(full) <= max_id_len:
        return full
    digest = hashlib.sha1(stem.encode()).hexdigest()[:6]
    short_suffix = f"__from_{digest}"
    candidate = name + short_suffix
    if len(candidate) <= max_id_len:
        return candidate
    head = name[: max_id_len - len(short_suffix)]
    return head + short_suffix


def _is_identical_test_dup(name: str, idx: _MoveIndex) -> bool:
    if name not in idx.source_funcs or name not in idx.target_funcs:
        return False
    return func_body_hash(idx.source_funcs[name]) == func_body_hash(
        idx.target_funcs[name]
    )


def _classify_units(
    unit_names: list[str],
    source: Path,
    target: Path,
    idx: _MoveIndex,
) -> tuple[list[str], list[str], dict[str, str]]:
    warnings: list[str] = []
    rename_map: dict[str, str] = {}
    final_units: list[str] = []
    for name in unit_names:
        if name not in idx.target_top_names:
            final_units.append(name)
            continue
        if _is_identical_test_dup(name, idx):
            warnings.append(
                f"dedup: dropped {source.name}::{name} "
                f"(identical body to {target.name}::{name})"
            )
            _delete_function_from_source(source, name)
            continue
        suffix = idx.cls_suffix if name in idx.source_class_names else idx.fn_suffix
        new_name = _bounded_rename(name, suffix, idx.stem)
        rename_map[name] = new_name
        final_units.append(new_name)
        warnings.append(
            f"rename: {source.name}::{name} -> {new_name} "
            f"(collision with {target.name})"
        )
    return warnings, final_units, rename_map


def _apply_helper_conflict_renames(
    source: Path,
    target: Path,
    project_path: Path,
    source_tree: ast.Module,
    target_tree: ast.Module,
    final_units: list[str],
    stem: str,
) -> list[str]:
    helper_renames = _resolve_helper_conflicts(
        source_tree,
        target_tree,
        final_units,
        stem,
        target=target,
        project_path=project_path,
    )
    if not helper_renames:
        return []
    _rename_name_in_module(source, helper_renames)
    return [
        f"helper-rename: {source.name}::{old} -> {new} "
        f"(body-mismatch with {target.name}::{old})"
        for old, new in sorted(helper_renames.items())
    ]


def _apply_conftest_shadow_renames(
    source: Path,
    target: Path,
    project_path: Path,
    source_tree: ast.Module,
    target_tree: ast.Module,
    final_units: list[str],
) -> tuple[list[str], ast.Module]:
    target_stem = target.stem.removeprefix("test_")
    target_local_renames = _resolve_conftest_shadowing(
        source_tree,
        target_tree,
        final_units,
        target,
        project_path,
        target_stem,
    )
    if not target_local_renames:
        return [], target_tree
    _rename_name_in_module(target, target_local_renames)
    new_target_tree = ast.parse(target.read_text())
    warnings = [
        f"target-helper-rename: {target.name}::{old} -> {new} "
        f"(shadowed conftest fixture needed by moved tests)"
        for old, new in sorted(target_local_renames.items())
    ]
    return warnings, new_target_tree


def _existing_top_level_names(tree: ast.Module) -> set[str]:
    """Names already bound at module top level (assignments + def/class)."""
    assigned = {n for stmt in tree.body for n in _stmt_assignment_targets(stmt)}
    defined = {
        n.name
        for n in tree.body
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
    }
    return assigned | defined


def _collect_dep_snippets(
    dep_names: list[str],
    existing: set[str],
    defs: dict[str, ast.stmt],
    pre_anvil_source_text: str,
) -> tuple[list[str], list[str]]:
    """Return ``(snippets, carried_names)`` for deps to inject into target."""
    snippets: list[str] = []
    carried: list[str] = []
    for name in dep_names:
        if name in existing:
            continue
        node = defs.get(name)
        if not isinstance(node, ast.Assign | ast.AnnAssign):
            continue
        segment = ast.get_source_segment(pre_anvil_source_text, node) or ast.unparse(
            node
        )
        snippets.append(segment)
        carried.append(name)
    return snippets, carried


def _copy_module_level_deps_to_target(
    source: Path,
    target: Path,
    pre_anvil_source_text: str,
    pre_anvil_source_tree: ast.Module,
    dep_names: list[str],
) -> list[str]:
    """Insert decorator-referenced module-level deps into target as text.

    Runs **after** anvil so the constants are absent from the new target
    (anvil only moved the test units). Source is left untouched, so when
    ``_finalize_split_anchor`` later renames source to the anchor target,
    those same constants are still present there too.
    """
    if not dep_names or not target.exists():
        return []
    target_text = target.read_text()
    target_tree = ast.parse(target_text)
    existing = _existing_top_level_names(target_tree)
    defs = _source_top_level_definitions(pre_anvil_source_tree)
    snippets, carried = _collect_dep_snippets(
        dep_names, existing, defs, pre_anvil_source_text
    )
    if not snippets:
        return []
    new_text = _insert_before_first_def(target_text, target_tree, snippets)
    target.write_text(new_text)
    return [
        f"decorator-followup: copying dep `{name}` to {target.name} "
        f"from {source.name} alongside its dependents"
        for name in carried
    ]


def _insert_before_first_def(
    target_text: str, target_tree: ast.Module, snippets: list[str]
) -> str:
    """Splice *snippets* into *target_text* right before the first def/class.

    Falls back to appending at end-of-file when the target contains no
    function/class definition (rare: a freshly-created split target may
    contain only a module docstring at this point).
    """
    block = "\n\n".join(snippets) + "\n\n"
    insert_line: int | None = None
    for stmt in target_tree.body:
        if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            insert_line = stmt.lineno
            if stmt.decorator_list:
                insert_line = min(d.lineno for d in stmt.decorator_list)
            break
    if insert_line is None:
        rstripped = target_text.rstrip()
        return f"{rstripped}\n\n{block.rstrip()}\n"
    lines = target_text.splitlines(keepends=True)
    head = "".join(lines[: insert_line - 1])
    tail = "".join(lines[insert_line - 1 :])
    return f"{head}{block}{tail}"


def _stmt_bound_names(stmt: ast.stmt) -> list[str]:
    """Names bound at the module top level by *stmt* (Name targets only)."""
    if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        return [stmt.name]
    if isinstance(stmt, ast.Assign):
        return [t.id for t in stmt.targets if isinstance(t, ast.Name)]
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        return [stmt.target.id]
    return []


def _stmt_load_eval_subnodes(stmt: ast.stmt) -> list[ast.AST]:
    """AST sub-nodes of *stmt* evaluated at module load."""
    if isinstance(stmt, ast.Assign):
        return [stmt.value]
    if isinstance(stmt, ast.AnnAssign):
        nodes: list[ast.AST] = [stmt.annotation]
        if stmt.value is not None:
            nodes.insert(0, stmt.value)
        return nodes
    if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef):
        return list(stmt.decorator_list)
    if isinstance(stmt, ast.ClassDef):
        return [
            *stmt.decorator_list,
            *stmt.bases,
            *(kw.value for kw in stmt.keywords),
        ]
    return []


def _stmt_load_time_refs(stmt: ast.stmt) -> set[str]:
    """Free ``Name(Load)`` references evaluated when *stmt* runs at module load.

    Body of ``FunctionDef``/``ClassDef`` is NOT load-evaluated, so it is
    intentionally skipped — only the decorator list (and ``bases`` /
    ``keywords`` for ClassDef) contributes load-time deps.
    """
    refs: set[str] = set()
    for node in _stmt_load_eval_subnodes(stmt):
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                refs.add(sub.id)
    return refs


def _module_level_dep_graph(
    tree: ast.Module,
) -> tuple[dict[str, ast.stmt], dict[str, set[str]]]:
    """Return ``(name -> stmt, name -> load-time deps)`` for top-level names.

    Spans Assign / AnnAssign / FunctionDef / AsyncFunctionDef / ClassDef.
    First binding wins on duplicate names (matches Python's left-to-right
    module exec).
    """
    name_to_stmt: dict[str, ast.stmt] = {}
    name_to_deps: dict[str, set[str]] = {}
    for stmt in tree.body:
        names = _stmt_bound_names(stmt)
        if not names:
            continue
        refs = _stmt_load_time_refs(stmt)
        for n in names:
            name_to_stmt.setdefault(n, stmt)
            name_to_deps.setdefault(n, set()).update(refs - {n})
    return name_to_stmt, name_to_deps


def _stmt_source_range(stmt: ast.stmt) -> tuple[int, int]:
    """Return 0-based (start, end) line range covering *stmt* incl. decorators."""
    start = stmt.lineno - 1
    if (
        isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        and stmt.decorator_list
    ):
        start = min(d.lineno for d in stmt.decorator_list) - 1
    end = stmt.end_lineno if stmt.end_lineno is not None else stmt.lineno
    return start, end


def _stmt_source_segment(text: str, stmt: ast.stmt) -> str:
    """Like ``ast.get_source_segment`` but includes preceding decorators."""
    if (
        isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        and stmt.decorator_list
    ):
        start, end = _stmt_source_range(stmt)
        lines = text.splitlines(keepends=True)
        return "".join(lines[start:end]).rstrip("\n")
    return ast.get_source_segment(text, stmt) or ast.unparse(stmt)


def _decorated_start_line(stmt: ast.stmt) -> int:
    if (
        isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        and stmt.decorator_list
    ):
        return min(d.lineno for d in stmt.decorator_list)
    return stmt.lineno


def _find_insert_line(body: list[ast.stmt], hoist_names: set[str]) -> int | None:
    for stmt in body:
        if _stmt_load_time_refs(stmt) & hoist_names:
            return _decorated_start_line(stmt)
    for stmt in body:
        if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            return _decorated_start_line(stmt)
    return None


def _insert_before_first_use(
    target_text: str,
    target_tree: ast.Module,
    snippets: list[str],
    hoist_names: set[str],
) -> str:
    """Splice *snippets* before the first stmt that load-time references
    a name in *hoist_names*. Falls back to before-first-def, then EOF.
    """
    block = "\n\n".join(snippets) + "\n\n"
    insert_line = _find_insert_line(target_tree.body, hoist_names)
    if insert_line is None:
        rstripped = target_text.rstrip()
        return f"{rstripped}\n\n{block.rstrip()}\n"
    lines = target_text.splitlines(keepends=True)
    head = "".join(lines[: insert_line - 1])
    tail = "".join(lines[insert_line - 1 :])
    return f"{head}{block}{tail}"


_BIG_ORDER = 10**6


def _collect_decorator_refs(tree: ast.Module) -> set[str]:
    refs: set[str] = set()
    for stmt in tree.body:
        if not isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        for dec in stmt.decorator_list:
            for sub in ast.walk(dec):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                    refs.add(sub.id)
    return refs


def _compute_hoist_closure(
    seed: set[str],
    target_names: set[str],
    stmt_to_deps: dict[str, set[str]],
) -> set[str]:
    hoist: set[str] = set()
    queue: list[str] = list(seed)
    while queue:
        name = queue.pop()
        if name in hoist:
            continue
        hoist.add(name)
        for dep in stmt_to_deps.get(name, set()):
            if dep in target_names and dep not in hoist:
                queue.append(dep)
    return hoist


def _build_source_order(pre_anvil_source_tree: ast.Module | None) -> dict[str, int]:
    source_order: dict[str, int] = {}
    if pre_anvil_source_tree is None:
        return source_order
    for i, stmt in enumerate(pre_anvil_source_tree.body):
        for n in _stmt_bound_names(stmt):
            source_order.setdefault(n, i)
    return source_order


def _stmt_hoist_dep_stmts(
    stmt: ast.stmt,
    hoist: set[str],
    name_to_hoist_stmt: dict[str, ast.stmt],
    stmt_to_deps: dict[str, set[str]],
) -> list[ast.stmt]:
    out: list[ast.stmt] = []
    for n in _stmt_bound_names(stmt):
        if n not in hoist:
            continue
        for dep in stmt_to_deps.get(n, set()):
            if dep in hoist:
                out.append(name_to_hoist_stmt[dep])
    return out


def _build_hoist_dag(
    hoist: set[str],
    hoist_stmts_by_id: dict[int, ast.stmt],
    name_to_hoist_stmt: dict[str, ast.stmt],
    stmt_to_deps: dict[str, set[str]],
) -> tuple[dict[int, set[int]], dict[int, int]]:
    successors: dict[int, set[int]] = {sid: set() for sid in hoist_stmts_by_id}
    in_degree: dict[int, int] = dict.fromkeys(hoist_stmts_by_id, 0)
    for stmt in hoist_stmts_by_id.values():
        sid = id(stmt)
        for dep_stmt in _stmt_hoist_dep_stmts(
            stmt, hoist, name_to_hoist_stmt, stmt_to_deps
        ):
            dsid = id(dep_stmt)
            if dsid == sid or sid in successors[dsid]:
                continue
            successors[dsid].add(sid)
            in_degree[sid] += 1
    return successors, in_degree


def _topo_linearise(
    hoist_stmts_by_id: dict[int, ast.stmt],
    successors: dict[int, set[int]],
    in_degree: dict[int, int],
    key: Callable[[ast.stmt], tuple[int, int]],
) -> list[ast.stmt]:
    ordered: list[ast.stmt] = []
    ready = sorted(
        [s for sid, s in hoist_stmts_by_id.items() if in_degree[sid] == 0],
        key=key,
    )
    while ready:
        s = ready.pop(0)
        ordered.append(s)
        for succ_sid in successors[id(s)]:
            in_degree[succ_sid] -= 1
            if in_degree[succ_sid] != 0:
                continue
            succ = hoist_stmts_by_id[succ_sid]
            succ_key = key(succ)
            i = 0
            while i < len(ready) and key(ready[i]) <= succ_key:
                i += 1
            ready.insert(i, succ)
    return ordered


def _first_use_line(
    tree: ast.Module, hoist_stmts_by_id: dict[int, ast.stmt], hoist: set[str]
) -> int | None:
    for stmt in tree.body:
        if id(stmt) in hoist_stmts_by_id:
            continue
        if not (_stmt_load_time_refs(stmt) & hoist):
            continue
        if (
            isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
            and stmt.decorator_list
        ):
            return min(d.lineno for d in stmt.decorator_list)
        return stmt.lineno
    return None


def _rewrite_with_hoist(
    target: Path,
    text: str,
    hoist_stmts_by_id: dict[int, ast.stmt],
    ordered: list[ast.stmt],
    hoist: set[str],
) -> list[str]:
    snippets = [_stmt_source_segment(text, s) for s in ordered]
    lines = text.splitlines(keepends=True)
    ranges = sorted(
        (_stmt_source_range(s) for s in hoist_stmts_by_id.values()),
        reverse=True,
    )
    new_lines = list(lines)
    for start, end in ranges:
        del new_lines[start:end]
    new_text = "".join(new_lines)
    try:
        new_tree = ast.parse(new_text)
    except SyntaxError:
        return []
    new_text = _insert_before_first_use(new_text, new_tree, snippets, hoist)
    target.write_text(new_text)
    return [f"decorator-order: restored module-level load order in {target.name}"]


@dataclass(frozen=True)
class _HoistPlan:
    text: str
    tree: ast.Module
    hoist: set[str]
    hoist_stmts_by_id: dict[int, ast.stmt]
    ordered: list[ast.stmt]


def _read_module(target: Path) -> tuple[str, ast.Module] | None:
    if not target.exists():
        return None
    text = target.read_text()
    try:
        return text, ast.parse(text)
    except SyntaxError:
        return None


def _plan_hoist(
    text: str, tree: ast.Module, pre_anvil_source_tree: ast.Module | None
) -> _HoistPlan | None:
    name_to_stmt, stmt_to_deps = _module_level_dep_graph(tree)
    if not name_to_stmt:
        return None
    target_names = set(name_to_stmt.keys())
    seed = _collect_decorator_refs(tree) & target_names
    if not seed:
        return None
    hoist = _compute_hoist_closure(seed, target_names, stmt_to_deps)
    hoist_stmts_by_id: dict[int, ast.stmt] = {
        id(name_to_stmt[n]): name_to_stmt[n] for n in hoist
    }
    if not hoist_stmts_by_id:
        return None

    source_order = _build_source_order(pre_anvil_source_tree)
    target_order: dict[int, int] = {id(s): i for i, s in enumerate(tree.body)}

    def _key(s: ast.stmt) -> tuple[int, int]:
        names = _stmt_bound_names(s)
        src = min((source_order.get(n, _BIG_ORDER) for n in names), default=_BIG_ORDER)
        return (src, target_order[id(s)])

    name_to_hoist_stmt: dict[str, ast.stmt] = {n: name_to_stmt[n] for n in hoist}
    successors, in_degree = _build_hoist_dag(
        hoist, hoist_stmts_by_id, name_to_hoist_stmt, stmt_to_deps
    )
    ordered = _topo_linearise(hoist_stmts_by_id, successors, in_degree, _key)
    if len(ordered) != len(hoist_stmts_by_id):
        return None
    return _HoistPlan(text, tree, hoist, hoist_stmts_by_id, ordered)


def _is_hoist_noop(plan: _HoistPlan) -> bool:
    current = [id(s) for s in plan.tree.body if id(s) in plan.hoist_stmts_by_id]
    desired = [id(s) for s in plan.ordered]
    first_use = _first_use_line(plan.tree, plan.hoist_stmts_by_id, plan.hoist)
    all_before_use = first_use is None or all(
        s.lineno < first_use for s in plan.hoist_stmts_by_id.values()
    )
    return current == desired and all_before_use


def _topological_reorder_decorator_deps(
    target: Path, pre_anvil_source_tree: ast.Module | None = None
) -> list[str]:
    """Reorder module-level statements in *target* so load-time deps land
    before their first use.

    **Target-centric**: the dependency graph is built from the target tree
    alone, spanning Assign / AnnAssign / FunctionDef / ClassDef. The
    pre-anvil source tree is used **only** as a stable tiebreaker between
    multiple valid topological linearisations — it is not load-bearing
    for correctness, which matters when a target receives content from
    multiple sources (no single ``pre_anvil_source_tree`` can describe
    all contributors).

    A statement is **hoisted** if its bound name is transitively
    referenced by any module-level decorator. Hoisted statements are
    placed (in topological order) before the first remaining statement
    that uses any hoisted name at load time. Statements outside the
    hoist set keep their relative position — the AC3 surgical guarantee.
    """
    parsed = _read_module(target)
    if parsed is None:
        return []
    text, tree = parsed
    plan = _plan_hoist(text, tree, pre_anvil_source_tree)
    if plan is None or _is_hoist_noop(plan):
        return []
    return _rewrite_with_hoist(
        target, plan.text, plan.hoist_stmts_by_id, plan.ordered, plan.hoist
    )


def _append_marker_fixtures(
    source: Path,
    target: Path,
    project_path: Path,
    target_tree: ast.Module,
    final_units: list[str],
) -> tuple[list[str], list[str]]:
    source_tree = ast.parse(source.read_text())
    extra_fixtures = _collect_marker_fixtures_to_move(
        source_tree, target_tree, final_units, project_path, target
    )
    # ``keep_in_source`` pins fixtures still needed by units that haven't
    # been moved yet; with ``shared_helpers="duplicate"`` anvil copies the
    # fixture into target AND leaves it in source while anything there
    # still references it. Don't subtract ``keep_in_source`` from
    # ``extra_fixtures`` — that previously caused subsequent split
    # targets to miss the fixture they declared via ``usefixtures``.
    if not extra_fixtures:
        return list(final_units), []
    merged = list(final_units) + sorted(extra_fixtures)
    warnings = [
        f"usefixtures-followup: moving fixture `{fx}` "
        f"from {source.name} alongside its dependents"
        for fx in sorted(extra_fixtures)
    ]
    return merged, warnings


def _filter_movable_units(
    source: Path, final_units: list[str]
) -> tuple[list[str], list[str]]:
    """Keep only names defined at the source module top level.

    A method name (e.g. ``test_basic`` declared inside a ``Test*`` class) is
    not a movable top-level symbol; passing it to ``move_symbols`` would
    crash the whole pipeline. Drop such names here and surface the cause as
    a pipeline warning rather than relying on anvil to tolerate bad input.
    """
    top_level = _existing_top_level_names(ast.parse(source.read_text()))
    movable = [name for name in final_units if name in top_level]
    warnings = [
        f"dropped non-movable unit `{name}`: not a top-level symbol in {source.name}"
        for name in final_units
        if name not in top_level
    ]
    return movable, warnings


def _finalize_move(
    source: Path,
    target: Path,
    project_path: Path,
    final_units: list[str],
) -> list[str]:
    assert move_symbols is not None, "axm-anvil not importable"
    movable_units, drop_warnings = _filter_movable_units(source, final_units)
    plan = move_symbols(
        source_path=source,
        target_path=target,
        symbol_names=movable_units,
        workspace_root=project_path,
        shared_helpers="duplicate",
    )
    warnings = list(drop_warnings)
    warnings.extend(plan.warnings)
    warnings.extend(_backfill_missing_imports(source, target, project_path))
    _reorder_module_statements(target)
    if source.exists():
        _reorder_module_statements(source)
    return warnings


def _safe_move_units(
    source: Path,
    target: Path,
    unit_names: list[str],
    project_path: Path,
    keep_in_source: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Move units from source to target, resolving cross-file name collisions.

    Strategy on each colliding name:
      * If both are test_* funcs and bodies identical → drop from source.
      * Otherwise → rename in source with suffix ``__from_<source_stem>``.

    ``keep_in_source`` is the set of fixture/helper names that must stay
    in source even if the moving units reference them — used by
    ``_execute_split`` to ensure the anchor (which will become target
    later via _git_mv) doesn't lose fixtures the non-anchor moves would
    otherwise duplicate-and-delete. The follow-up
    ``_collect_marker_fixtures_to_move`` excludes these names; anvil
    sees them as still-used by remaining source content and leaves
    the definitions alone.

    Returns (warnings, actually_moved_names) — moved names are the
    final names anvil received (possibly with suffix).
    """
    if not unit_names:
        return [], []
    assert move_symbols is not None, "axm-anvil not importable"
    idx = _build_move_index(source, target)
    warnings, final_units, rename_map = _classify_units(unit_names, source, target, idx)
    if rename_map:
        _rename_top_level_in_source(source, rename_map)
    if not final_units:
        return warnings, []

    source_tree = ast.parse(source.read_text())
    warnings.extend(
        _apply_helper_conflict_renames(
            source,
            target,
            project_path,
            source_tree,
            idx.target_tree,
            final_units,
            idx.stem,
        )
    )

    shadow_warnings, target_tree = _apply_conftest_shadow_renames(
        source,
        target,
        project_path,
        source_tree,
        idx.target_tree,
        final_units,
    )
    warnings.extend(shadow_warnings)

    pre_anvil_source_text = source.read_text()
    pre_anvil_source_tree = ast.parse(pre_anvil_source_text)
    module_deps_to_copy = _collect_module_level_deps_to_copy(
        pre_anvil_source_tree, target_tree, final_units, project_path, target
    )

    final_units, fixture_warnings = _append_marker_fixtures(
        source, target, project_path, target_tree, final_units
    )
    warnings.extend(fixture_warnings)

    warnings.extend(_finalize_move(source, target, project_path, final_units))

    warnings.extend(
        _copy_module_level_deps_to_target(
            source,
            target,
            pre_anvil_source_text,
            pre_anvil_source_tree,
            module_deps_to_copy,
        )
    )
    warnings.extend(_topological_reorder_decorator_deps(target, pre_anvil_source_tree))
    return warnings, final_units
