"""Post-pipeline polish: collapse duplicated test helpers.

After SPLIT and MERGE leave anvil's ``shared_helpers="duplicate"`` copies
of helpers (gold_project, _make_result, …) in every post-move file, this
module collapses them into a single ``tests/<tier>/_helpers.py`` (for
pure helpers) or the tier's ``conftest.py`` (for ``@pytest.fixture``).

Three layers:

* ``extract_shared_helpers`` — top-level entry; iterates ``_once``
  until fixed-point, deduplicating ambiguous-fixture warnings across
  iterations.
* ``extract_shared_helpers_once`` / ``_in_tier`` — single-pass
  extraction across all canonical tiers.
* ``load_or_create_*`` / ``strip_def_*`` — file-level mutation
  helpers, libcst-based.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import libcst as cst

from .cst_rewrite import (
    _backfill_missing_imports,
    _dedupe_imports_cst,
    _is_cst_import,
)
from .io_primitives import cst_load, cst_save
from .paths import module_path_for_test_file
from .tests_ast import (
    _const_value_hash,
    _helper_body_hash,
    _is_pytest_fixture,
    _references_file_dunder,
    _source_segment_with_decorators,
)

__all__ = [
    "extract_shared_helpers",
    "extract_shared_helpers_in_tier",
    "extract_shared_helpers_once",
    "load_or_create_conftest_module",
    "load_or_create_helpers_module",
    "strip_def_and_inject_import",
    "strip_def_only",
]


_EXTRACT_MAX_ITERS = 10

# (src_text, body_hash, kind)
_HelperEntry = tuple[str, str, str]
# (body_hash, kind, files) per duplicate group
_HelperGroup = tuple[str, str, list[Path]]
_HelperSig = tuple[str, str, str]


@dataclass
class _TierScan:
    """Result of scanning a tier directory for candidate top-level defs."""

    per_file: dict[Path, dict[str, _HelperEntry]] = field(default_factory=dict)
    location_skipped: set[str] = field(default_factory=set)


@dataclass
class _TierIndex:
    """Indexed view of a tier scan, grouped by name with dependency edges."""

    by_name: dict[str, list[_HelperGroup]] = field(default_factory=dict)
    deps_by_name: dict[str, set[str]] = field(default_factory=dict)


@dataclass
class _DupPartition:
    """Duplicates eligible for extraction plus skip diagnostics."""

    duplicates: dict[_HelperSig, list[Path]] = field(default_factory=dict)
    skip_msgs: list[str] = field(default_factory=list)
    skipped_names: set[str] = field(default_factory=set)


@dataclass
class _EmitTargets:
    """File paths and CST modules into which helpers/fixtures get extracted."""

    helpers_path: Path
    conftest_path: Path
    helpers_module_path: str
    helpers_module: cst.Module
    conftest_module: cst.Module


def extract_shared_helpers(project_path: Path) -> list[str]:
    """Iterate ``extract_shared_helpers_once`` until fixed-point.

    A single pass cannot catch every duplicate: promoting helper A can
    expose helper B as duplicate (e.g. A's body referenced B locally,
    so B looked non-shared until A moved out). Loop until no further
    extraction happens. Capped at ``_EXTRACT_MAX_ITERS`` to fail loud
    on a buggy fixed-point.

    ``ambiguous fixture`` messages are re-emitted on every iteration
    (the same fixtures stay ambiguous forever) — collapse them so the
    operator sees each one exactly once.
    """
    all_msgs: list[str] = []
    seen_ambiguous: set[str] = set()
    for _ in range(_EXTRACT_MAX_ITERS):
        msgs = extract_shared_helpers_once(project_path)
        progress = [m for m in msgs if "ambiguous fixture" not in m]
        deduped: list[str] = list(progress)
        for m in msgs:
            if "ambiguous fixture" in m and m not in seen_ambiguous:
                seen_ambiguous.add(m)
                deduped.append(m)
        all_msgs.extend(deduped)
        if not progress:
            break
    return all_msgs


def extract_shared_helpers_once(project_path: Path) -> list[str]:
    """Promote helpers duplicated across a tier into ``tests/<tier>/_helpers.py``."""
    msgs: list[str] = []
    tests_root = project_path / "tests"
    if not tests_root.is_dir():
        return msgs
    for tier in ("integration", "e2e", "unit"):
        tier_dir = tests_root / tier
        if not tier_dir.is_dir():
            continue
        msgs.extend(extract_shared_helpers_in_tier(project_path, tier_dir))
    return msgs


def _classify_assign(
    node: ast.Assign, location_skipped: set[str]
) -> _HelperEntry | None:
    if len(node.targets) != 1:
        return None
    tgt = node.targets[0]
    if not (isinstance(tgt, ast.Name) and tgt.id.isupper()):
        return None
    if _references_file_dunder(node.value):
        location_skipped.add(tgt.id)
        return None
    return tgt.id, _const_value_hash(node), "pure"


def _classify_top_level_node(
    node: ast.stmt, location_skipped: set[str]
) -> tuple[str, str, str] | None:
    """Return ``(name, body_hash, kind)`` for a candidate top-level def, else None.

    Mutates *location_skipped* with names rejected because they reference
    ``__file__`` — those names still participate in cascade analysis.
    """
    if isinstance(node, ast.FunctionDef):
        if node.name.startswith("test_"):
            return None
        kind = "fixture" if _is_pytest_fixture(node) else "pure"
        return node.name, _helper_body_hash(node), kind
    if isinstance(node, ast.ClassDef):
        if node.name.startswith("Test"):
            return None
        return node.name, _helper_body_hash(node), "pure"
    if isinstance(node, ast.Assign):
        return _classify_assign(node, location_skipped)
    return None


def _scan_tier(tier_dir: Path) -> _TierScan:
    """Walk *tier_dir* and collect candidate top-level defs per file."""
    scan = _TierScan()
    skip_names = {"__init__.py", "conftest.py", "_helpers.py"}
    for py in tier_dir.rglob("*.py"):
        if py.name in skip_names:
            continue
        try:
            text = py.read_text()
            tree = ast.parse(text)
        except (SyntaxError, OSError):
            continue
        helpers: dict[str, _HelperEntry] = {}
        for node in tree.body:
            classified = _classify_top_level_node(node, scan.location_skipped)
            if classified is None:
                continue
            name, body_hash, kind = classified
            src_seg = _source_segment_with_decorators(text, node)
            if src_seg is None:
                continue
            helpers[name] = (src_seg, body_hash, kind)
        if helpers:
            scan.per_file[py] = helpers
    return scan


def _index_tier_scan(scan: _TierScan) -> _TierIndex:
    """Group helpers by name and compute first-party dependency edges."""
    by_signature: dict[_HelperSig, list[Path]] = defaultdict(list)
    for py, helpers in scan.per_file.items():
        for h_name, (_, body_hash, kind) in helpers.items():
            by_signature[(h_name, body_hash, kind)].append(py)

    by_name: dict[str, list[_HelperGroup]] = defaultdict(list)
    for (h_name, body_hash, kind), files in by_signature.items():
        by_name[h_name].append((body_hash, kind, files))

    known_names = set(by_name) | scan.location_skipped
    deps_by_name: dict[str, set[str]] = defaultdict(set)
    for helpers_dict in scan.per_file.values():
        for h_name, (src_text, _hash, _kind) in helpers_dict.items():
            try:
                sub_tree = ast.parse(src_text)
            except SyntaxError:
                continue
            referenced = {
                n.id
                for n in ast.walk(sub_tree)
                if isinstance(n, ast.Name) and n.id != h_name
            }
            deps_by_name[h_name] |= referenced & known_names
    return _TierIndex(by_name=dict(by_name), deps_by_name=dict(deps_by_name))


def _format_ambiguous_skip(
    h_name: str, groups: list[_HelperGroup], project_path: Path
) -> str:
    kinds = {k for _, k, _ in groups}
    kind_label = (
        "fixture" if "fixture" in kinds else "helper" if "pure" in kinds else "constant"
    )
    body_lines = []
    for idx, (body_hash, _kind, files) in enumerate(groups, 1):
        files_rel = sorted(str(f.relative_to(project_path)) for f in files)
        body_lines.append(
            f"    body#{idx} ({body_hash[:8]}, {len(files)} file(s)): "
            + ", ".join(files_rel)
        )
    file_count = sum(len(files) for _, _, files in groups)
    return (
        f"ambiguous {kind_label} `{h_name}` not extracted: "
        f"{len(groups)} divergent bodies across {file_count} files "
        "(likely intentional override or signature drift — review manually):\n"
        + "\n".join(body_lines)
        + "\n    Resolution: keep each body where its callers "
        "depend on it, or unify the bodies and remove the "
        "others; consumers of the wrong body fail silently "
        "with state-mismatch / TypeError, not ImportError."
    )


def _partition_duplicates(index: _TierIndex, project_path: Path) -> _DupPartition:
    """Split indexed helpers into extractable duplicates vs ambiguous skips."""
    part = _DupPartition()
    for h_name, groups in index.by_name.items():
        if len(groups) > 1:
            groups.sort(key=lambda g: (-len(g[2]), g[0]))
            part.skip_msgs.append(_format_ambiguous_skip(h_name, groups, project_path))
            part.skipped_names.add(h_name)
            continue
        groups.sort(key=lambda g: (-len(g[2]), g[0]))
        winning_hash, winning_kind, winning_files = groups[0]
        if len(winning_files) < 2:
            continue
        part.duplicates[(h_name, winning_hash, winning_kind)] = winning_files
    return part


def _drop_cascaded_dup(part: _DupPartition, h_name: str, blockers: set[str]) -> bool:
    """Remove first duplicate sig matching *h_name*; return True if dropped."""
    for sig in list(part.duplicates):
        if sig[0] != h_name:
            continue
        del part.duplicates[sig]
        part.skip_msgs.append(
            f"cascading skip `{h_name}` not extracted: "
            f"references skipped name(s) {sorted(blockers)} — "
            "extracting it alone would NameError at import time."
        )
        part.skipped_names.add(h_name)
        return True
    return False


def _resolve_cascading_skips(part: _DupPartition, index: _TierIndex) -> None:
    """Drop duplicates whose dependencies are skipped, until fixed-point."""
    changed = True
    while changed:
        changed = False
        for h_name, refs in index.deps_by_name.items():
            if h_name in part.skipped_names:
                continue
            blockers = refs & part.skipped_names
            if blockers and _drop_cascaded_dup(part, h_name, blockers):
                changed = True


def _build_emit_targets(project_path: Path, tier_dir: Path) -> _EmitTargets | None:
    helpers_path = tier_dir / "_helpers.py"
    conftest_path = tier_dir.parent / "conftest.py"
    helpers_module_path = module_path_for_test_file(helpers_path, project_path)
    if helpers_module_path is None:
        return None
    helpers_module = load_or_create_helpers_module(
        helpers_path, tier_dir.name, helpers_module_path
    )
    conftest_module = load_or_create_conftest_module(conftest_path)
    if helpers_module is None or conftest_module is None:
        return None
    return _EmitTargets(
        helpers_path=helpers_path,
        conftest_path=conftest_path,
        helpers_module_path=helpers_module_path,
        helpers_module=helpers_module,
        conftest_module=conftest_module,
    )


@dataclass
class _EmitState:
    """Mutable accumulator threaded through per-duplicate emission."""

    helpers_body: list[cst.BaseStatement]
    conftest_body: list[cst.BaseStatement]
    helpers_existing: set[str]
    conftest_existing: set[str]
    helpers_touched: bool = False
    conftest_touched: bool = False
    msgs: list[str] = field(default_factory=list)


def _existing_def_names(module: cst.Module) -> set[str]:
    return {
        s.name.value
        for s in module.body
        if isinstance(s, cst.FunctionDef | cst.ClassDef)
    }


def _emit_one_fixture(
    state: _EmitState,
    targets: _EmitTargets,
    name: str,
    files: list[Path],
    parsed: Sequence[cst.BaseStatement | cst.SimpleStatementLine],
    project_path: Path,
) -> None:
    if name not in state.conftest_existing:
        state.conftest_body.extend(parsed)
        state.conftest_existing.add(name)
        state.conftest_touched = True
        state.msgs.append(
            f"extracted fixture `{name}` -> "
            f"{targets.conftest_path.relative_to(project_path)} "
            f"(was duplicated in {len(files)} files)"
        )
    for f in files:
        strip_def_only(f, name)


def _emit_one_helper(
    state: _EmitState,
    targets: _EmitTargets,
    name: str,
    files: list[Path],
    parsed: Sequence[cst.BaseStatement | cst.SimpleStatementLine],
    project_path: Path,
) -> None:
    if name not in state.helpers_existing:
        state.helpers_body.extend(parsed)
        state.helpers_existing.add(name)
        state.helpers_touched = True
        state.msgs.append(
            f"extracted helper `{name}` -> "
            f"{targets.helpers_path.relative_to(project_path)} "
            f"(was duplicated in {len(files)} files)"
        )
    for f in files:
        strip_def_and_inject_import(f, name, targets.helpers_module_path, project_path)


def _flush_emit_state(
    state: _EmitState,
    targets: _EmitTargets,
    per_file: dict[Path, dict[str, _HelperEntry]],
    project_path: Path,
) -> None:
    if state.helpers_touched:
        cst_save(
            targets.helpers_path,
            targets.helpers_module.with_changes(body=state.helpers_body),
        )
    if state.conftest_touched:
        cst_save(
            targets.conftest_path,
            targets.conftest_module.with_changes(body=state.conftest_body),
        )
    donor = next(iter(per_file.keys()), None)
    if donor is None:
        return
    if state.helpers_touched:
        state.msgs.extend(
            _backfill_missing_imports(donor, targets.helpers_path, project_path)
        )
    if state.conftest_touched:
        state.msgs.extend(
            _backfill_missing_imports(donor, targets.conftest_path, project_path)
        )


def _emit_duplicates(
    targets: _EmitTargets,
    duplicates: dict[_HelperSig, list[Path]],
    per_file: dict[Path, dict[str, _HelperEntry]],
    project_path: Path,
) -> list[str]:
    """Append each extracted helper/fixture to its module and strip callers."""
    state = _EmitState(
        helpers_body=list(targets.helpers_module.body),
        conftest_body=list(targets.conftest_module.body),
        helpers_existing=_existing_def_names(targets.helpers_module),
        conftest_existing=_existing_def_names(targets.conftest_module),
    )
    for (name, _, kind), files in sorted(duplicates.items(), key=lambda kv: kv[0][0]):
        canonical_src = per_file[sorted(files)[0]][name][0]
        try:
            parsed = cst.parse_module(canonical_src).body
        except cst.ParserSyntaxError:
            continue
        if kind == "fixture":
            _emit_one_fixture(state, targets, name, files, parsed, project_path)
        else:
            _emit_one_helper(state, targets, name, files, parsed, project_path)
    _flush_emit_state(state, targets, per_file, project_path)
    return state.msgs


def extract_shared_helpers_in_tier(project_path: Path, tier_dir: Path) -> list[str]:
    """Process a single tier. Splitting per-tier keeps imports local."""
    scan = _scan_tier(tier_dir)
    index = _index_tier_scan(scan)
    part = _partition_duplicates(index, project_path)
    part.skipped_names |= scan.location_skipped
    _resolve_cascading_skips(part, index)
    if not part.duplicates and not part.skip_msgs:
        return []
    if not part.duplicates:
        return part.skip_msgs
    targets = _build_emit_targets(project_path, tier_dir)
    if targets is None:
        return []
    msgs = _emit_duplicates(targets, part.duplicates, scan.per_file, project_path)
    msgs.extend(part.skip_msgs)
    return msgs


def load_or_create_helpers_module(
    helpers_path: Path, tier_name: str, helpers_module_path: str
) -> cst.Module | None:
    if helpers_path.exists():
        return cst_load(helpers_path)
    return cst.parse_module(
        f'"""Shared helpers for ``tests/{tier_name}``.\n\n'
        "Promoted from duplicate top-level defs found across files.\n"
        f"Import explicitly: ``from {helpers_module_path} import <name>``.\n"
        '"""\n\n'
        "from __future__ import annotations\n"
    )


def load_or_create_conftest_module(conftest_path: Path) -> cst.Module | None:
    if conftest_path.exists():
        return cst_load(conftest_path)
    return cst.parse_module(
        '"""Pytest fixtures auto-discovered by tests in this directory.\n\n'
        "Promoted from duplicate ``@pytest.fixture`` definitions originally\n"
        "scattered across multiple test files.\n"
        '"""\n\n'
        "from __future__ import annotations\n"
    )


def strip_def_only(file: Path, name: str) -> None:
    """Remove the top-level def of *name* from *file* without injecting an import.

    Used for fixtures whose new home (``conftest.py``) is auto-discovered
    by pytest — no import would be valid syntactically (it would shadow
    the injected fixture parameter) and none is needed.
    """
    module = cst_load(file)
    if module is None:
        return
    new_body: list[cst.BaseStatement] = []
    stripped = False
    for stmt in module.body:
        if isinstance(stmt, cst.FunctionDef | cst.ClassDef) and stmt.name.value == name:
            stripped = True
            continue
        new_body.append(stmt)
    if stripped:
        cst_save(file, module.with_changes(body=new_body))


def _is_top_level_assign_to(stmt: cst.BaseStatement, name: str) -> bool:
    if not isinstance(stmt, cst.SimpleStatementLine) or len(stmt.body) != 1:
        return False
    assign = stmt.body[0]
    if not isinstance(assign, cst.Assign) or len(assign.targets) != 1:
        return False
    target = assign.targets[0].target
    return isinstance(target, cst.Name) and target.value == name


def _is_module_docstring(stmt: cst.BaseStatement) -> bool:
    if not isinstance(stmt, cst.SimpleStatementLine) or len(stmt.body) != 1:
        return False
    expr = stmt.body[0]
    return isinstance(expr, cst.Expr) and isinstance(
        expr.value, cst.SimpleString | cst.ConcatenatedString
    )


def _compute_import_insert_index(body: list[cst.BaseStatement]) -> int:
    insert_at = 0
    for idx, stmt in enumerate(body):
        if not (_is_cst_import(stmt) or _is_module_docstring(stmt)):
            break
        insert_at = idx + 1
    return insert_at


def strip_def_and_inject_import(
    file: Path, name: str, helpers_module: str, project_path: Path
) -> None:
    """Remove the top-level def of ``name`` from *file* and import it instead."""
    module = cst_load(file)
    if module is None:
        return
    new_body: list[cst.BaseStatement] = []
    stripped = False
    for stmt in module.body:
        if isinstance(stmt, cst.FunctionDef | cst.ClassDef) and stmt.name.value == name:
            stripped = True
            continue
        if _is_top_level_assign_to(stmt, name):
            stripped = True
            continue
        new_body.append(stmt)
    if not stripped:
        return
    import_stmt = cst.parse_statement(f"from {helpers_module} import {name}")
    assert isinstance(import_stmt, cst.SimpleStatementLine)
    new_body.insert(_compute_import_insert_index(new_body), import_stmt)
    new_module = module.with_changes(body=new_body)
    new_module = _dedupe_imports_cst(new_module)
    cst_save(file, new_module)
