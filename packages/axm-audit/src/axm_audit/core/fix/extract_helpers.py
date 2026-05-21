"""Post-pipeline polish: collapse duplicated test helpers.

After SPLIT and MERGE leave anvil's ``shared_helpers="duplicate"`` copies
of helpers (gold_project, _make_result, …) in every post-move file, this
module collapses them into a single ``tests/<tier>/_helpers.py`` (for
pure helpers) or the tier's ``conftest.py`` (for ``@pytest.fixture``).

Three layers:

* ``_extract_shared_helpers`` — top-level entry; iterates ``_once``
  until fixed-point, deduplicating ambiguous-fixture warnings across
  iterations.
* ``_extract_shared_helpers_once`` / ``_in_tier`` — single-pass
  extraction across all canonical tiers.
* ``_load_or_create_*`` / ``_strip_def_*`` — file-level mutation
  helpers, libcst-based.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

import libcst as cst

from .cst_rewrite import (
    _backfill_missing_imports,
    _dedupe_imports_cst,
    _is_cst_import,
)
from .io_primitives import _cst_load, _cst_save
from .paths import _module_path_for_test_file
from .tests_ast import (
    _const_value_hash,
    _helper_body_hash,
    _is_pytest_fixture,
    _references_file_dunder,
    _source_segment_with_decorators,
)

__all__ = [
    "_extract_shared_helpers",
    "_extract_shared_helpers_in_tier",
    "_extract_shared_helpers_once",
    "_load_or_create_conftest_module",
    "_load_or_create_helpers_module",
    "_strip_def_and_inject_import",
    "_strip_def_only",
]


_EXTRACT_MAX_ITERS = 10


def _extract_shared_helpers(project_path: Path) -> list[str]:
    """Iterate ``_extract_shared_helpers_once`` until fixed-point.

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
        msgs = _extract_shared_helpers_once(project_path)
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


def _extract_shared_helpers_once(project_path: Path) -> list[str]:
    """Promote helpers duplicated across a tier into ``tests/<tier>/_helpers.py``."""
    msgs: list[str] = []
    tests_root = project_path / "tests"
    if not tests_root.is_dir():
        return msgs
    for tier in ("integration", "e2e", "unit"):
        tier_dir = tests_root / tier
        if not tier_dir.is_dir():
            continue
        msgs.extend(_extract_shared_helpers_in_tier(project_path, tier_dir))
    return msgs


def _extract_shared_helpers_in_tier(project_path: Path, tier_dir: Path) -> list[str]:
    """Process a single tier. Splitting per-tier keeps imports local."""
    per_file: dict[Path, dict[str, tuple[str, str, str]]] = {}
    location_skipped_names: set[str] = set()
    for py in tier_dir.rglob("*.py"):
        if py.name in {"__init__.py", "conftest.py", "_helpers.py"}:
            continue
        try:
            text = py.read_text()
            tree = ast.parse(text)
        except (SyntaxError, OSError):
            continue
        helpers: dict[str, tuple[str, str, str]] = {}
        for node in tree.body:
            name: str | None = None
            body_hash: str | None = None
            kind: str = "pure"
            if isinstance(node, ast.FunctionDef):
                if node.name.startswith("test_"):
                    continue
                name, body_hash = node.name, _helper_body_hash(node)
                if _is_pytest_fixture(node):
                    kind = "fixture"
            elif isinstance(node, ast.ClassDef):
                if node.name.startswith("Test"):
                    continue
                name, body_hash = node.name, _helper_body_hash(node)
            elif isinstance(node, ast.Assign) and len(node.targets) == 1:
                tgt = node.targets[0]
                if isinstance(tgt, ast.Name) and tgt.id.isupper():
                    if _references_file_dunder(node.value):
                        location_skipped_names.add(tgt.id)
                        continue
                    name, body_hash = tgt.id, _const_value_hash(node)
            if name is None or body_hash is None:
                continue
            src_seg = _source_segment_with_decorators(text, node)
            if src_seg is None:
                continue
            helpers[name] = (src_seg, body_hash, kind)
        if helpers:
            per_file[py] = helpers

    by_signature: dict[tuple[str, str, str], list[Path]] = defaultdict(list)
    for py, helpers in per_file.items():
        for h_name, (_, body_hash, kind) in helpers.items():
            by_signature[(h_name, body_hash, kind)].append(py)

    skip_msgs: list[str] = []
    skipped_names: set[str] = set(location_skipped_names)
    by_name: dict[str, list[tuple[str, str, list[Path]]]] = defaultdict(list)
    for (h_name, body_hash, kind), files in by_signature.items():
        by_name[h_name].append((body_hash, kind, files))

    deps_by_name: dict[str, set[str]] = defaultdict(set)
    known_names = set(by_name) | location_skipped_names
    for py, helpers_dict in per_file.items():
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

    duplicates: dict[tuple[str, str, str], list[Path]] = {}
    for h_name, groups in by_name.items():
        kinds = {k for _, k, _ in groups}
        if len(groups) > 1:
            groups.sort(key=lambda g: (-len(g[2]), g[0]))
            kind_label = (
                "fixture"
                if "fixture" in kinds
                else "helper"
                if "pure" in kinds
                else "constant"
            )
            body_lines = []
            for idx, (body_hash, _kind, files) in enumerate(groups, 1):
                files_rel = sorted(str(f.relative_to(project_path)) for f in files)
                body_lines.append(
                    f"    body#{idx} ({body_hash[:8]}, {len(files)} file(s)): "
                    + ", ".join(files_rel)
                )
            file_count = sum(len(files) for _, _, files in groups)
            skip_msgs.append(
                f"ambiguous {kind_label} `{h_name}` not extracted: "
                f"{len(groups)} divergent bodies across {file_count} files "
                "(likely intentional override or signature drift — "
                "review manually):\n"
                + "\n".join(body_lines)
                + "\n    Resolution: keep each body where its callers "
                "depend on it, or unify the bodies and remove the "
                "others; consumers of the wrong body fail silently "
                "with state-mismatch / TypeError, not ImportError."
            )
            skipped_names.add(h_name)
            continue
        groups.sort(key=lambda g: (-len(g[2]), g[0]))
        winning_hash, winning_kind, winning_files = groups[0]
        if len(winning_files) < 2:
            continue
        duplicates[(h_name, winning_hash, winning_kind)] = winning_files

    changed = True
    while changed:
        changed = False
        for h_name, refs in deps_by_name.items():
            if h_name in skipped_names:
                continue
            cascade_blockers = refs & skipped_names
            if cascade_blockers:
                for sig in list(duplicates):
                    if sig[0] == h_name:
                        del duplicates[sig]
                        skip_msgs.append(
                            f"cascading skip `{h_name}` not extracted: "
                            f"references skipped name(s) "
                            f"{sorted(cascade_blockers)} — extracting it "
                            "alone would NameError at import time."
                        )
                        skipped_names.add(h_name)
                        changed = True
                        break

    if not duplicates and not skip_msgs:
        return []
    if not duplicates:
        return skip_msgs
    msgs: list[str] = []
    helpers_path = tier_dir / "_helpers.py"
    conftest_path = tier_dir.parent / "conftest.py"
    helpers_module_path = _module_path_for_test_file(helpers_path, project_path)
    if helpers_module_path is None:
        return []
    helpers_module = _load_or_create_helpers_module(
        helpers_path, tier_dir.name, helpers_module_path
    )
    conftest_module = _load_or_create_conftest_module(conftest_path)
    if helpers_module is None or conftest_module is None:
        return []
    helpers_existing = {
        s.name.value
        for s in helpers_module.body
        if isinstance(s, cst.FunctionDef | cst.ClassDef)
    }
    conftest_existing = {
        s.name.value
        for s in conftest_module.body
        if isinstance(s, cst.FunctionDef | cst.ClassDef)
    }
    helpers_body = list(helpers_module.body)
    conftest_body = list(conftest_module.body)
    helpers_touched = False
    conftest_touched = False
    sorted_dups = sorted(duplicates.items(), key=lambda kv: kv[0][0])
    for (name, _, kind), files in sorted_dups:
        canonical_file = sorted(files)[0]
        canonical_src = per_file[canonical_file][name][0]
        try:
            parsed = cst.parse_module(canonical_src).body
        except cst.ParserSyntaxError:
            continue
        if kind == "fixture":
            if name not in conftest_existing:
                conftest_body.extend(parsed)
                conftest_existing.add(name)
                conftest_touched = True
                msgs.append(
                    f"extracted fixture `{name}` -> "
                    f"{conftest_path.relative_to(project_path)} "
                    f"(was duplicated in {len(files)} files)"
                )
            for f in files:
                _strip_def_only(f, name)
        else:
            if name not in helpers_existing:
                helpers_body.extend(parsed)
                helpers_existing.add(name)
                helpers_touched = True
                msgs.append(
                    f"extracted helper `{name}` -> "
                    f"{helpers_path.relative_to(project_path)} "
                    f"(was duplicated in {len(files)} files)"
                )
            for f in files:
                _strip_def_and_inject_import(f, name, helpers_module_path, project_path)
    if helpers_touched:
        _cst_save(helpers_path, helpers_module.with_changes(body=helpers_body))
    if conftest_touched:
        _cst_save(conftest_path, conftest_module.with_changes(body=conftest_body))
    donor = next(iter(per_file.keys()), None)
    if donor is not None:
        if helpers_touched:
            msgs.extend(_backfill_missing_imports(donor, helpers_path, project_path))
        if conftest_touched:
            msgs.extend(_backfill_missing_imports(donor, conftest_path, project_path))
    msgs.extend(skip_msgs)
    return msgs


def _load_or_create_helpers_module(
    helpers_path: Path, tier_name: str, helpers_module_path: str
) -> cst.Module | None:
    if helpers_path.exists():
        return _cst_load(helpers_path)
    return cst.parse_module(
        f'"""Shared helpers for ``tests/{tier_name}``.\n\n'
        "Promoted from duplicate top-level defs found across files.\n"
        f"Import explicitly: ``from {helpers_module_path} import <name>``.\n"
        '"""\n\n'
        "from __future__ import annotations\n"
    )


def _load_or_create_conftest_module(conftest_path: Path) -> cst.Module | None:
    if conftest_path.exists():
        return _cst_load(conftest_path)
    return cst.parse_module(
        '"""Pytest fixtures auto-discovered by tests in this directory.\n\n'
        "Promoted from duplicate ``@pytest.fixture`` definitions originally\n"
        "scattered across multiple test files.\n"
        '"""\n\n'
        "from __future__ import annotations\n"
    )


def _strip_def_only(file: Path, name: str) -> None:
    """Remove the top-level def of *name* from *file* without injecting an import.

    Used for fixtures whose new home (``conftest.py``) is auto-discovered
    by pytest — no import would be valid syntactically (it would shadow
    the injected fixture parameter) and none is needed.
    """
    module = _cst_load(file)
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
        _cst_save(file, module.with_changes(body=new_body))


def _strip_def_and_inject_import(
    file: Path, name: str, helpers_module: str, project_path: Path
) -> None:
    """Remove the top-level def of ``name`` from *file* and import it instead."""
    module = _cst_load(file)
    if module is None:
        return
    new_body: list[cst.BaseStatement] = []
    stripped = False
    for stmt in module.body:
        if isinstance(stmt, cst.FunctionDef | cst.ClassDef) and stmt.name.value == name:
            stripped = True
            continue
        if (
            isinstance(stmt, cst.SimpleStatementLine)
            and len(stmt.body) == 1
            and isinstance(stmt.body[0], cst.Assign)
            and len(stmt.body[0].targets) == 1
            and isinstance(stmt.body[0].targets[0].target, cst.Name)
            and stmt.body[0].targets[0].target.value == name
        ):
            stripped = True
            continue
        new_body.append(stmt)
    if not stripped:
        return
    import_stmt = cst.parse_statement(f"from {helpers_module} import {name}")
    assert isinstance(import_stmt, cst.SimpleStatementLine)
    insert_at = 0
    for idx, stmt in enumerate(new_body):
        if _is_cst_import(stmt) or (
            isinstance(stmt, cst.SimpleStatementLine)
            and len(stmt.body) == 1
            and isinstance(stmt.body[0], cst.Expr)
            and isinstance(
                stmt.body[0].value,
                cst.SimpleString | cst.ConcatenatedString,
            )
        ):
            insert_at = idx + 1
        else:
            break
    new_body.insert(insert_at, import_stmt)
    new_module = module.with_changes(body=new_body)
    new_module = _dedupe_imports_cst(new_module)
    _cst_save(file, new_module)
