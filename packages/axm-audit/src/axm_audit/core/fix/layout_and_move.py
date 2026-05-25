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
import subprocess
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
from .paths import _file_depth_from_project, _module_path_for_test_file
from .tests_ast import (
    _collect_conftest_fixtures,
    _collect_marker_fixtures_to_move,
    _func_body_hash,
    _marker_fixtures_in_unit,
    _names_referenced_in_unit,
    _string_literal_fixtures_in_unit,
    _top_level_helpers,
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


def _iter_non_canonical_tier_dirs(tests_root: Path) -> list[Path]:
    out: list[Path] = []
    for child in sorted(tests_root.iterdir()):
        if not child.is_dir() or child.name in CANONICAL_TIERS:
            continue
        if child.name.startswith(("_", ".")):
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
    old_mod = _module_path_for_test_file(src, project_path)
    depth_delta = _file_depth_from_project(
        target, project_path
    ) - _file_depth_from_project(src, project_path)
    _git_mv(src, target)
    if depth_delta != 0:
        msgs.extend(_patch_file_dunder_depth(target, depth_delta))
    new_mod = _module_path_for_test_file(target, project_path)
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
    MERGE / RENAME because ``_tier_for_path`` returns ``None`` for them.

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


def _flatten_single_tier(project_path: Path, tier_dir: Path) -> list[str]:
    """Move every nested ``test_*.py`` under *tier_dir* up to *tier_dir* root."""
    msgs: list[str] = []
    nested = sorted(
        p for p in tier_dir.rglob("test_*.py") if p.is_file() and p.parent != tier_dir
    )
    if not nested:
        return msgs
    for src in nested:
        rel_parents = src.relative_to(tier_dir).parts[:-1]
        target = tier_dir / src.name
        old_mod = _module_path_for_test_file(src, project_path)
        if target.exists() and target != src:
            prefix = "_".join(rel_parents)
            stem = src.stem.removeprefix("test_")
            target = tier_dir / f"test_{prefix}_{stem}.py"
            counter = 2
            while target.exists():
                target = tier_dir / f"test_{prefix}_{stem}_{counter}.py"
                counter += 1
        src_depth = _file_depth_from_project(src, project_path)
        tgt_depth = _file_depth_from_project(target, project_path)
        _git_mv(src, target)
        depth_delta = tgt_depth - src_depth
        if depth_delta != 0:
            msgs.extend(_patch_file_dunder_depth(target, depth_delta))
        new_mod = _module_path_for_test_file(target, project_path)
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
    _prune_empty_test_subdirs(tier_dir)
    return msgs


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
        if sub == tier_dir:
            continue
        has_test = any(
            f.is_file() and f.name.startswith("test_") and f.suffix == ".py"
            for f in sub.iterdir()
        )
        if has_test:
            continue
        for f in sub.iterdir():
            if f.is_file():
                rc = subprocess.run(
                    ["git", "rm", "-q", str(f)],
                    capture_output=True,
                    text=True,
                )
                if rc.returncode != 0:
                    f.unlink()
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
    source_helpers = _top_level_helpers(source_tree)
    target_helpers = _top_level_helpers(target_tree)
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
        | _marker_fixtures_in_unit(node)
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
    moving = set(moving_unit_names)
    moving_nodes = [
        n
        for n in source_tree.body
        if isinstance(n, ast.FunctionDef | ast.ClassDef) and n.name in moving
    ]
    if not moving_nodes:
        return {}
    referenced: set[str] = set()
    for node in moving_nodes:
        referenced |= _names_referenced_in_unit(node)
        referenced |= _marker_fixtures_in_unit(node)
        referenced |= _string_literal_fixtures_in_unit(node)
    source_helpers = _top_level_helpers(source_tree)
    target_helpers = _top_level_helpers(target_tree)
    conftest_fixtures = _collect_conftest_fixtures(target, project_path)
    rename: dict[str, str] = {}
    suffix = f"__local_{target_stem}"
    for name in sorted(referenced):
        if name in source_helpers:
            continue
        if name not in target_helpers:
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
    source_tree = ast.parse(source.read_text())
    target_tree = ast.parse(target.read_text())
    target_top_names = {
        n.name
        for n in target_tree.body
        if isinstance(n, ast.FunctionDef | ast.ClassDef)
    }
    source_funcs = {
        n.name: n
        for n in source_tree.body
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    }
    target_funcs = {
        n.name: n
        for n in target_tree.body
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    }

    warnings: list[str] = []
    rename_map: dict[str, str] = {}
    final_units: list[str] = []
    stem = source.stem.removeprefix("test_")
    fn_suffix = f"__from_{stem}"
    cls_suffix = "From" + "".join(p.capitalize() for p in stem.split("_") if p)
    source_class_names = {
        n.name for n in source_tree.body if isinstance(n, ast.ClassDef)
    }

    def _bounded_rename(name: str, suffix: str) -> str:
        """Compose ``name + suffix``, shrinking the suffix's stem if the
        full identifier would push the eventual ``def <name>(...) -> ...``
        line past ruff's 88-char limit. Falls back to a 6-char hash of
        the original stem so name uniqueness survives the truncation.
        """
        full = name + suffix
        # 88 - len("def ") - len("(") - safety margin (=10 for ``( ... )``)
        # gives us room of ~73 for the identifier itself.
        max_id_len = 73
        if len(full) <= max_id_len:
            return full
        # Build a shorter suffix. Anchor on a 6-char hash of the stem so
        # different source files produce distinct suffixes.
        import hashlib

        digest = hashlib.sha1(stem.encode()).hexdigest()[:6]
        short_suffix = f"__from_{digest}"
        candidate = name + short_suffix
        if len(candidate) <= max_id_len:
            return candidate
        # If even the digest suffix overflows, truncate the name itself
        # (very rare — test names already at 65+ chars). Keep last 4
        # chars of name + digest for stability.
        head = name[: max_id_len - len(short_suffix)]
        return head + short_suffix

    for name in unit_names:
        if name not in target_top_names:
            final_units.append(name)
            continue
        if name in source_funcs and name in target_funcs:
            if _func_body_hash(source_funcs[name]) == _func_body_hash(
                target_funcs[name]
            ):
                warnings.append(
                    f"dedup: dropped {source.name}::{name} "
                    f"(identical body to {target.name}::{name})"
                )
                _delete_function_from_source(source, name)
                continue
        suffix = cls_suffix if name in source_class_names else fn_suffix
        new_name = _bounded_rename(name, suffix)
        rename_map[name] = new_name
        final_units.append(new_name)
        warnings.append(
            f"rename: {source.name}::{name} -> {new_name} "
            f"(collision with {target.name})"
        )

    if rename_map:
        _rename_top_level_in_source(source, rename_map)

    if not final_units:
        return warnings, []

    source_tree = ast.parse(source.read_text())
    helper_renames = _resolve_helper_conflicts(
        source_tree,
        target_tree,
        final_units,
        stem,
        target=target,
        project_path=project_path,
    )
    if helper_renames:
        _rename_name_in_module(source, helper_renames)
        for old, new in sorted(helper_renames.items()):
            warnings.append(
                f"helper-rename: {source.name}::{old} -> {new} "
                f"(body-mismatch with {target.name}::{old})"
            )

    target_stem = target.stem.removeprefix("test_")
    target_local_renames = _resolve_conftest_shadowing(
        source_tree,
        target_tree,
        final_units,
        target,
        project_path,
        target_stem,
    )
    if target_local_renames:
        _rename_name_in_module(target, target_local_renames)
        target_tree = ast.parse(target.read_text())
        for old, new in sorted(target_local_renames.items()):
            warnings.append(
                f"target-helper-rename: {target.name}::{old} -> {new} "
                f"(shadowed conftest fixture needed by moved tests)"
            )

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
    if extra_fixtures:
        final_units = list(final_units) + sorted(extra_fixtures)
        for fx in sorted(extra_fixtures):
            warnings.append(
                f"usefixtures-followup: moving fixture `{fx}` "
                f"from {source.name} alongside its dependents"
            )

    plan = move_symbols(
        source_path=source,
        target_path=target,
        symbol_names=final_units,
        workspace_root=project_path,
        shared_helpers="duplicate",
    )
    warnings.extend(plan.warnings)
    backfilled = _backfill_missing_imports(source, target, project_path)
    warnings.extend(backfilled)
    _reorder_module_statements(target)
    if source.exists():
        _reorder_module_statements(source)
    return warnings, final_units
