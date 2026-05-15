"""Prototype: deterministic test-suite auto-fixer.

Pipeline (4 stages, all deterministic; NO_PACKAGE_SYMBOL is reported but
left to a human/agent — its verdict is context-dependent):

    1. RELOCATE   (PYRAMID_LEVEL mismatch)              git mv across tiers
    2. SPLIT      (FILE_NAMING verdict=SPLIT)           axm_anvil.move_symbols
    3. COLLIDE    (FILE_NAMING verdict=COLLIDE)         axm_anvil.move_symbols
    4. RENAME     (FILE_NAMING verdict=NAME_MISMATCH)   git mv

The chain re-audits between stage 1 and stages 2-4 so SPLIT/MERGE/RENAME
act on post-RELOCATE paths.

This proto **consumes findings emitted by the rules** (AXM-1721 +
AXM-1722). No tuple detection inlined; the rules are the source of truth.

Companion to:
  * tuple_naming_proto.py       — historical integration tuple detector
  * tuple_naming_e2e_proto.py   — historical e2e CLI tuple detector
  * README_E2E_SESSION.md       — context

Usage::

    uv run --python 3.12 python tuple_fix_proto.py /tmp/proto-fix/axm-audit-copy
    uv run --python 3.12 python tuple_fix_proto.py <path> --apply
    uv run --python 3.12 python tuple_fix_proto.py <path> --rules=TEST_QUALITY_FILE_NAMING

The script defaults to --dry-run.  Pass --apply to actually mutate.
"""

from __future__ import annotations

import argparse
import ast
import shutil
import subprocess
import sys
import tomllib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from axm_audit.core.auditor import audit_project
from axm_audit.core.rules.test_quality._shared import (
    canonical_filename,
    cli_invocation_tuple,
    first_party_symbol_counts,
    get_pkg_prefixes,
)

try:
    from axm_anvil.core.move import move_symbols
except ImportError:  # pragma: no cover
    move_symbols = None  # type: ignore[assignment]

NON_DETERMINISTIC_RULES = frozenset(
    {
        # NO_PACKAGE_SYMBOL: a test that exercises no package symbol may
        # be a legitimate formal check on an artefact, or a candidate for
        # deletion. The verdict is context-dependent — use /scenario-rename
        # or inspect manually.
        "TEST_QUALITY_NO_PACKAGE_SYMBOL",
    }
)


# ---------------------------------------------------------------------------
# FileOp model
# ---------------------------------------------------------------------------


OpKind = Literal["flatten", "relocate", "split", "merge", "rename"]


@dataclass
class FileOp:
    kind: OpKind
    source: Path
    target: Path | list[Path]
    rationale: str
    source_rule: str
    # SPLIT: tuple keyed by the canonical filename a test belongs to →
    # list of test_* names that should land in that file.
    split_map: dict[str, list[str]] | None = None


@dataclass
class PipelineReport:
    ops: list[FileOp] = field(default_factory=list)
    unfixable: list[dict[str, Any]] = field(default_factory=list)
    applied: bool = False
    warnings: list[str] = field(default_factory=list)

    def by_kind(self) -> dict[str, int]:
        c: Counter[str] = Counter()
        for op in self.ops:
            c[op.kind] += 1
        return dict(c)


# ---------------------------------------------------------------------------
# Finding extraction
# ---------------------------------------------------------------------------


def _findings(check: Any) -> list[dict[str, Any]]:
    """Normalise a CheckResult's findings into a list[dict]."""
    raw = None
    if hasattr(check, "details") and isinstance(check.details, dict):
        raw = check.details.get("findings")
    if raw is None:
        raw = getattr(check, "findings", None)
    if not raw:
        return []
    out: list[dict[str, Any]] = []
    for f in raw:
        if isinstance(f, dict):
            out.append(f)
        elif hasattr(f, "model_dump"):
            out.append(f.model_dump())
        else:
            out.append(vars(f))
    return out


def _abspath(p: str, project_path: Path) -> Path:
    """Normalise a finding path (which may be relative or absolute)."""
    pp = Path(p)
    return pp if pp.is_absolute() else (project_path / pp)


def _check_by_rule(project_path: Path, rule_id: str) -> list[dict[str, Any]]:
    result = audit_project(project_path, category="test_quality")
    for check in result.checks:
        if getattr(check, "rule_id", "") == rule_id:
            out = _findings(check)
            # Normalise path fields to absolute Path strings
            for d in out:
                for key in ("path", "test_file"):
                    if key in d and isinstance(d[key], str) and d[key]:
                        d[key] = str(_abspath(d[key], project_path))
                if "files" in d and isinstance(d["files"], list):
                    d["files"] = [
                        str(_abspath(f, project_path)) if isinstance(f, str) else f
                        for f in d["files"]
                    ]
            return out
    return []


# ---------------------------------------------------------------------------
# Stage 1: RELOCATE (PYRAMID_LEVEL)
# ---------------------------------------------------------------------------


def _retier(p: Path, root: Path, target_lvl: str) -> Path:
    """Compute the destination path under tests/{target_lvl}/.

    Walks the relative parts: replaces ``tests/<X>/...rest...`` by
    ``tests/<target_lvl>/...rest...``.  Tolerates absent root prefix.
    """
    rel = p.relative_to(root) if p.is_absolute() else p
    parts = list(rel.parts)
    if len(parts) >= 2 and parts[0] == "tests":
        parts[1] = target_lvl
    return root / Path(*parts)


def plan_flatten(project_path: Path) -> list[FileOp]:
    """Stage 0: detect Test* classes with divergent method tuples → flatten.

    A class whose methods don't all share the same canonical tuple is not
    a movable unit. We flatten it to top-level functions so SPLIT can
    route each method to its correct target file. Pathological classes
    (using ``self.x``, inheriting non-object, having __init__) cannot be
    flattened deterministically and emit an out-of-pipeline warning.
    """
    findings = _check_by_rule(project_path, "TEST_QUALITY_FILE_NAMING")
    ops: list[FileOp] = []
    pkg_prefixes = get_pkg_prefixes(project_path)
    scripts = _load_project_scripts(project_path)
    single_binary = next(iter(scripts)) if len(scripts) == 1 else None
    # Only files flagged by FILE_NAMING are candidates (avoids scanning
    # every test_* in the project).
    candidate_paths: set[Path] = set()
    for d in findings:
        if d.get("verdict") in {"SPLIT", "COLLIDE", "NAME_MISMATCH"}:
            p = Path(d.get("path", ""))
            if p.is_absolute() and p.exists():
                candidate_paths.add(p)
            elif d.get("files"):
                for fp in d["files"]:
                    pp = Path(fp)
                    if pp.is_absolute() and pp.exists():
                        candidate_paths.add(pp)
    for src in sorted(candidate_paths):
        tier_str = src.parent.name
        if tier_str not in ("integration", "e2e"):
            continue
        tree = ast.parse(src.read_text())
        classes_to_flatten: list[str] = []
        pathological: list[tuple[str, str]] = []
        for cls in _top_level_test_classes(tree):
            if not _class_needs_flatten(
                cls, tree, tier=tier_str, pkg_prefixes=pkg_prefixes,
                scripts=scripts, single_binary=single_binary,
            ):
                continue
            reason = _class_is_pathological(cls)
            if reason is not None:
                pathological.append((cls.name, reason))
            else:
                classes_to_flatten.append(cls.name)
        if classes_to_flatten:
            ops.append(
                FileOp(
                    kind="flatten",
                    source=src,
                    target=src,
                    rationale=(
                        f"flatten {len(classes_to_flatten)} heterogeneous "
                        f"class(es): {classes_to_flatten}"
                    ),
                    source_rule="TEST_QUALITY_FILE_NAMING",
                    split_map={c: [] for c in classes_to_flatten},
                )
            )
        for cname, why in pathological:
            ops.append(
                FileOp(
                    kind="flatten",
                    source=src,
                    target=src,
                    rationale=f"PATHOLOGICAL {cname}: {why} — cannot flatten",
                    source_rule="TEST_QUALITY_FILE_NAMING",
                )
            )
    return ops


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
    return [f"flatten: rewrote {op.source.name} ({list(op.split_map.keys())})"]


def plan_relocate(project_path: Path) -> list[FileOp]:
    """Aggregate PYRAMID_LEVEL findings → 1 op per homogeneous file.

    A file whose tests classify into N≠1 distinct target levels is skipped
    (requires manual split; out of pipeline).
    """
    findings = _check_by_rule(project_path, "TEST_QUALITY_PYRAMID_LEVEL")
    per_file: dict[Path, Counter[str]] = defaultdict(Counter)
    for d in findings:
        cur, lvl = d.get("current_level"), d.get("level")
        if cur == lvl or lvl is None:
            continue
        per_file[Path(d["path"])][lvl] += 1
    ops: list[FileOp] = []
    for p, target_levels in per_file.items():
        if len(target_levels) != 1:
            continue  # mixed; needs split first
        target_lvl = next(iter(target_levels))
        n = target_levels[target_lvl]
        ops.append(
            FileOp(
                kind="relocate",
                source=p,
                target=_retier(p, project_path, target_lvl),
                rationale=f"{n} test(s) classify as {target_lvl}",
                source_rule="TEST_QUALITY_PYRAMID_LEVEL",
            )
        )
    return ops


# ---------------------------------------------------------------------------
# Stages 2-4: FILE_NAMING (SPLIT / COLLIDE / NAME_MISMATCH)
# ---------------------------------------------------------------------------


def plan_naming(project_path: Path) -> tuple[list[FileOp], list[FileOp], list[FileOp]]:
    """Read FILE_NAMING findings → (splits, merges, renames).

    Returns the three stages in *execution* order.  Each stage is mutually
    exclusive on a given file: a SPLIT victim doesn't get a RENAME (its
    children inherit canonical names from the split), and a COLLIDE victim
    doesn't get a RENAME (the merge target already has the canonical name).
    """
    findings = _check_by_rule(project_path, "TEST_QUALITY_FILE_NAMING")
    splits: list[FileOp] = []
    merges: list[FileOp] = []
    renames: list[FileOp] = []

    # Bucket by verdict
    by_verdict: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for d in findings:
        by_verdict[d.get("verdict", "")].append(d)

    # Files that will be touched by SPLIT or COLLIDE → exempt from RENAME
    consumed: set[Path] = set()

    # 2. SPLIT
    for d in by_verdict.get("SPLIT", []):
        src = Path(d["path"])
        consumed.add(src)
        # AXM-1722 should expose `suggested_splits` (list of canonical names);
        # if absent, fall back to the file's `tuple` field flattened.
        suggested = d.get("suggested_splits") or [d.get("proposed_name", "")]
        suggested = [s for s in suggested if s]
        targets = [src.parent / s for s in suggested]
        splits.append(
            FileOp(
                kind="split",
                source=src,
                target=targets,
                rationale=f"{len(targets)} distinct tuples",
                source_rule="TEST_QUALITY_FILE_NAMING",
                split_map=d.get("split_map"),
            )
        )

    # 3. COLLIDE — one finding per collision group; pick lexically-first as anchor
    for d in by_verdict.get("COLLIDE", []):
        files = sorted(Path(p) for p in d.get("files", []))
        if len(files) < 2:
            continue
        anchor = files[0]
        for other in files[1:]:
            consumed.add(other)
            merges.append(
                FileOp(
                    kind="merge",
                    source=other,
                    target=anchor,
                    rationale=f"COLLIDE on {d.get('canonical_name', '?')} in tests/{d.get('tier', '?')}/",
                    source_rule="TEST_QUALITY_FILE_NAMING",
                )
            )

    # 4. RENAME — skip files consumed by stages 2/3
    for d in by_verdict.get("NAME_MISMATCH", []):
        src = Path(d["path"])
        if src in consumed:
            continue
        proposed = d.get("proposed_name", "")
        if not proposed or src.name == proposed:
            continue
        renames.append(
            FileOp(
                kind="rename",
                source=src,
                target=src.parent / proposed,
                rationale=f"{src.name} -> {proposed}",
                source_rule="TEST_QUALITY_FILE_NAMING",
            )
        )

    return splits, merges, renames


# ---------------------------------------------------------------------------
# Unfixable surfacing
# ---------------------------------------------------------------------------


def collect_unfixable(project_path: Path) -> list[dict[str, Any]]:
    """Re-audit and return NO_PACKAGE_SYMBOL findings.

    Defensive: post-apply, axm-audit's internal AST cache may hold stale
    paths if files were renamed in-flight. Swallow that exception — the
    caller (proto reporter) treats absence as "no unfixable findings".
    """
    try:
        result = audit_project(project_path, category="test_quality")
    except FileNotFoundError:
        return []
    out: list[dict[str, Any]] = []
    for check in result.checks:
        rid = getattr(check, "rule_id", "")
        if rid not in NON_DETERMINISTIC_RULES:
            continue
        for d in _findings(check):
            out.append({"rule_id": rid, **d})
    return out


# ---------------------------------------------------------------------------
# Executors
# ---------------------------------------------------------------------------


def _git_mv(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    rc = subprocess.run(
        ["git", "mv", str(src), str(dst)],
        capture_output=True,
        text=True,
    )
    if rc.returncode != 0:
        shutil.move(str(src), str(dst))


def _execute_relocate(op: FileOp) -> None:
    assert isinstance(op.target, Path)
    _git_mv(op.source, op.target)


def _execute_rename(op: FileOp) -> None:
    assert isinstance(op.target, Path)
    _git_mv(op.source, op.target)


TOP_K = 2


def _walk_test_funcs(tree: ast.Module) -> list[ast.FunctionDef]:
    """Return test_* funcs at module level and inside Test* classes."""
    funcs: list[ast.FunctionDef] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            funcs.append(node)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name.startswith(
                    "test_"
                ):
                    funcs.append(child)
    return funcs


def _top_level_test_names(tree: ast.Module) -> set[str]:
    """test_* function names at module level only (no class methods)."""
    return {
        n.name
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    }


def _top_level_test_classes(tree: ast.Module) -> list[ast.ClassDef]:
    """Test* classes at module level that contain test_* methods."""
    out: list[ast.ClassDef] = []
    for node in tree.body:
        if not (isinstance(node, ast.ClassDef) and node.name.startswith("Test")):
            continue
        if any(
            isinstance(c, ast.FunctionDef) and c.name.startswith("test_")
            for c in node.body
        ):
            out.append(node)
    return out


def _class_is_pathological(cls: ast.ClassDef) -> str | None:
    """Return a reason if the class cannot be safely flattened, else None.

    Pathological = uses `self.<attr>` inside methods, has `__init__`,
    inherits from anything other than `object` (or empty bases).
    """
    if cls.bases:
        for b in cls.bases:
            if not (isinstance(b, ast.Name) and b.id == "object"):
                return f"inherits from non-object base ({ast.unparse(b)})"
    for child in cls.body:
        if isinstance(child, ast.FunctionDef) and child.name == "__init__":
            return "has __init__"
    # Detect `self.<attr>` reads/writes — these would break a flatten
    for child in cls.body:
        if not (isinstance(child, ast.FunctionDef) and child.name.startswith("test_")):
            continue
        for sub in ast.walk(child):
            if (
                isinstance(sub, ast.Attribute)
                and isinstance(sub.value, ast.Name)
                and sub.value.id == "self"
            ):
                return f"method {child.name} accesses self.{sub.attr}"
    return None


def _load_project_scripts(pkg_root: Path) -> set[str]:
    pyproject = pkg_root / "pyproject.toml"
    if not pyproject.exists():
        return set()
    data = tomllib.loads(pyproject.read_text())
    scripts = data.get("project", {}).get("scripts", {})
    return set(scripts.keys()) if isinstance(scripts, dict) else set()


def _func_canonical(
    func: ast.FunctionDef,
    tree: ast.Module,
    *,
    tier: Literal["integration", "e2e"],
    pkg_prefixes: set[str],
    scripts: set[str],
    single_binary: str | None,
) -> str:
    """Canonical filename a single test function would land in."""
    if tier == "integration":
        sym_counts = first_party_symbol_counts(
            test_func=func, mod_ast=tree, pkg_prefixes=pkg_prefixes
        )
        top: list[Any] = sorted(s for s, _ in sym_counts.most_common()[:TOP_K])
    else:
        inv_counts = cli_invocation_tuple(
            test_func=func, mod_ast=tree, project_scripts=scripts
        )
        top = sorted(t for t, _ in inv_counts.most_common()[:TOP_K])
    return canonical_filename(
        symbols_or_tuples=top, tier=tier, single_binary=single_binary
    )


def _per_unit_canonical(
    source: Path,
    tier: Literal["integration", "e2e"],
    project_path: Path,
) -> dict[str, list[str]]:
    """For each *movable unit*, compute its canonical filename.

    A movable unit is:
      * a top-level test_* function (anvil moves it directly), OR
      * a Test* class whose methods all share the same tuple (anvil moves
        the class as a block).

    Test* classes with divergent method tuples are NOT a single unit — the
    caller should flatten them first (Stage 0) and re-run.

    Returns {canonical_name: [unit_names]}.
    """
    tree = ast.parse(source.read_text())
    pkg_prefixes = get_pkg_prefixes(project_path)
    scripts = _load_project_scripts(project_path)
    single_binary = next(iter(scripts)) if len(scripts) == 1 else None
    routes: dict[str, list[str]] = defaultdict(list)
    # Top-level funcs
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            name = _func_canonical(
                node, tree, tier=tier, pkg_prefixes=pkg_prefixes,
                scripts=scripts, single_binary=single_binary,
            )
            routes[name].append(node.name)
    # Test* classes — only if homogeneous (else caller should flatten)
    for cls in _top_level_test_classes(tree):
        method_canonicals = {
            _func_canonical(
                c, tree, tier=tier, pkg_prefixes=pkg_prefixes,
                scripts=scripts, single_binary=single_binary,
            )
            for c in cls.body
            if isinstance(c, ast.FunctionDef) and c.name.startswith("test_")
        }
        if len(method_canonicals) == 1:
            routes[next(iter(method_canonicals))].append(cls.name)
        # else: divergent — handled by Stage 0 flatten
    return dict(routes)


def _class_needs_flatten(
    cls: ast.ClassDef,
    tree: ast.Module,
    *,
    tier: Literal["integration", "e2e"],
    pkg_prefixes: set[str],
    scripts: set[str],
    single_binary: str | None,
) -> bool:
    """True iff this class's methods have ≥2 distinct canonical filenames."""
    canonicals = {
        _func_canonical(
            c, tree, tier=tier, pkg_prefixes=pkg_prefixes,
            scripts=scripts, single_binary=single_binary,
        )
        for c in cls.body
        if isinstance(c, ast.FunctionDef) and c.name.startswith("test_")
    }
    return len(canonicals) >= 2


def _flatten_class_to_top_level(source_text: str, class_name: str) -> str:
    """Transform `class TestX: def test_a(self, ...): ...` into top-level funcs.

    Removes the class wrapper; promotes each test_* method by dropping
    `self` from its parameter list. Decorators on methods are preserved.
    Other bodies inside the class (helpers, fixtures) are also promoted
    to top-level — they may conflict with module-level names; caller is
    expected to verify with _class_is_pathological first.
    """
    tree = ast.parse(source_text)
    new_body: list[ast.stmt] = []
    for node in tree.body:
        if not (
            isinstance(node, ast.ClassDef) and node.name == class_name
        ):
            new_body.append(node)
            continue
        for child in node.body:
            if isinstance(child, ast.FunctionDef):
                # Drop `self` parameter if present
                args = child.args
                if args.args and args.args[0].arg == "self":
                    args.args = args.args[1:]
                new_body.append(child)
            elif isinstance(child, ast.Expr) and isinstance(
                child.value, ast.Constant
            ):
                # docstring — drop (it was the class docstring)
                pass
            else:
                new_body.append(child)
    tree.body = new_body
    return ast.unparse(tree) + "\n"


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
    tier_str = op.source.parent.name
    if tier_str not in ("integration", "e2e"):
        return [f"split skipped: source not under tests/integration|e2e ({op.source})"]
    if not op.source.exists():
        return [f"split skipped: source missing ({op.source})"]
    tree = ast.parse(op.source.read_text())
    # Sanity check: Stage 0 should have flattened heterogeneous classes
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
        return [
            f"split skipped: {op.source.name} still has heterogeneous "
            f"Test* classes after Stage 0: {leftover} (likely pathological)"
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
    for canonical, unit_names in routes.items():
        if canonical == anchor:
            continue
        target = op.source.parent / canonical
        if not target.exists():
            target.write_text(
                f'"""Tests for canonical tuple ``{canonical}`` — split from '
                f"{op.source.name}.\"\"\"\n"
            )
        plan = move_symbols(
            source_path=op.source,
            target_path=target,
            symbol_names=unit_names,
            workspace_root=project_path,
            shared_helpers="duplicate",
        )
        warnings.extend(plan.warnings)
    if op.source.exists() and op.source.name != anchor:
        _git_mv(op.source, op.source.parent / anchor)
    return warnings


def _func_body_hash(func: ast.FunctionDef) -> str:
    """Stable string hash of a function body (for collision dedup).

    Comparison is structural via ast.unparse on the body — ignores
    docstrings, comments, and minor formatting.
    """
    body = list(func.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]  # drop docstring
    stub = ast.Module(body=body, type_ignores=[])
    return ast.unparse(stub)


def _movable_units_at_top_level(tree: ast.Module) -> list[str]:
    """All top-level names anvil would move: test_* funcs + Test* classes."""
    out: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            out.append(node.name)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            out.append(node.name)
    return out


def _execute_merge(op: FileOp, project_path: Path) -> list[str]:
    """MERGE source's units into target via move_symbols.

    Strategy on name collision:
      * If source's test body is structurally identical to target's
        (after stripping docstrings), it's a duplicate — drop from source.
      * Otherwise, rename source's test with suffix ``__from_<source_stem>``
        and proceed.
    """
    assert move_symbols is not None, "axm-anvil not importable"
    assert isinstance(op.target, Path)
    if not op.source.exists() or not op.target.exists():
        return [f"merge skipped: missing ({op.source} -> {op.target})"]
    source_tree = ast.parse(op.source.read_text())
    target_tree = ast.parse(op.target.read_text())

    source_units = _movable_units_at_top_level(source_tree)
    if not source_units:
        return [f"merge skipped: {op.source} has no top-level movable units"]

    # Index target test bodies by name (for dedup decisions)
    target_funcs = {
        n.name: n
        for n in target_tree.body
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    }
    target_classes = {
        n.name: n
        for n in target_tree.body
        if isinstance(n, ast.ClassDef) and n.name.startswith("Test")
    }
    source_funcs = {
        n.name: n
        for n in source_tree.body
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    }

    warnings: list[str] = []
    rename_map: dict[str, str] = {}
    units_to_move: list[str] = []
    suffix = f"__from_{op.source.stem.replace('test_', '', 1)}"

    for name in source_units:
        if name in target_funcs and name in source_funcs:
            # Body comparison: drop duplicate, suffix divergent
            if _func_body_hash(source_funcs[name]) == _func_body_hash(
                target_funcs[name]
            ):
                warnings.append(
                    f"merge: dropped duplicate test {op.source.name}::{name} "
                    f"(identical to {op.target.name}::{name})"
                )
                _delete_function_from_source(op.source, name)
                continue
            new_name = name + suffix
            rename_map[name] = new_name
            units_to_move.append(name)
            warnings.append(
                f"merge: renamed {op.source.name}::{name} -> {new_name} "
                f"(name collision with {op.target.name}, divergent body)"
            )
        elif name in target_classes or name in target_funcs:
            # Class vs func collision, or class-class: rename
            new_name = name + suffix
            rename_map[name] = new_name
            units_to_move.append(name)
            warnings.append(
                f"merge: renamed {op.source.name}::{name} -> {new_name} "
                f"(name collision with {op.target.name})"
            )
        else:
            units_to_move.append(name)

    if not units_to_move:
        # Everything was duplicate — just drop the source file
        _delete_source_if_empty_tests(op.source)
        return warnings

    # Rename in-source first (anvil's `rename=` validates target absence
    # under the ORIGINAL name, so it can't resolve collisions itself).
    if rename_map:
        _rename_top_level_in_source(op.source, rename_map)
        units_to_move = [rename_map.get(n, n) for n in units_to_move]

    plan = move_symbols(
        source_path=op.source,
        target_path=op.target,
        symbol_names=units_to_move,
        workspace_root=project_path,
        shared_helpers="duplicate",
    )
    warnings.extend(plan.warnings)
    _delete_source_if_empty_tests(op.source)
    return warnings


def _delete_function_from_source(source: Path, func_name: str) -> None:
    """Remove a top-level FunctionDef from source by rewriting the AST."""
    tree = ast.parse(source.read_text())
    tree.body = [
        n
        for n in tree.body
        if not (isinstance(n, ast.FunctionDef) and n.name == func_name)
    ]
    source.write_text(ast.unparse(tree) + "\n")


def _rename_top_level_in_source(source: Path, old_to_new: dict[str, str]) -> None:
    """Rename top-level FunctionDef / ClassDef in *source* via AST rewrite.

    This is a workaround for axm-anvil's ``rename=`` parameter, which
    validates target absence under the ORIGINAL name before applying the
    rename — so it cannot resolve cross-file collisions on its own.
    By renaming in source first, we hand anvil a clean conflict-free move.
    """
    if not old_to_new:
        return
    tree = ast.parse(source.read_text())
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.ClassDef) and node.name in old_to_new:
            node.name = old_to_new[node.name]
    source.write_text(ast.unparse(tree) + "\n")


def _delete_source_if_empty_tests(source: Path) -> None:
    """git rm the source if no test_* funcs/classes remain."""
    if not source.exists():
        return
    tree = ast.parse(source.read_text())
    if _walk_test_funcs(tree):
        return
    rc = subprocess.run(
        ["git", "rm", "-q", str(source)],
        capture_output=True,
        text=True,
    )
    if rc.returncode != 0:
        source.unlink()


def execute(ops: list[FileOp], project_path: Path) -> list[str]:
    """Apply ops in order. Returns aggregated warnings."""
    warnings: list[str] = []
    for op in ops:
        if op.kind == "flatten":
            warnings.extend(_execute_flatten(op, project_path))
        elif op.kind == "relocate":
            _execute_relocate(op)
        elif op.kind == "rename":
            _execute_rename(op)
        elif op.kind == "split":
            warnings.extend(_execute_split(op, project_path))
        elif op.kind == "merge":
            warnings.extend(_execute_merge(op, project_path))
    return warnings


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def run(
    project_path: Path, *, apply: bool, rules: set[str]
) -> PipelineReport:
    report = PipelineReport(applied=apply)

    warnings: list[str] = []

    # Stage 0: FLATTEN heterogeneous Test* classes (FILE_NAMING preflight).
    # Done first so RELOCATE / SPLIT / MERGE / RENAME see top-level units only.
    if "TEST_QUALITY_FILE_NAMING" in rules:
        flatten_ops = plan_flatten(project_path)
        report.ops.extend(flatten_ops)
        if apply and flatten_ops:
            warnings.extend(execute(flatten_ops, project_path))

    # Stage 1: RELOCATE
    if "TEST_QUALITY_PYRAMID_LEVEL" in rules:
        relocate_ops = plan_relocate(project_path)
        report.ops.extend(relocate_ops)
        if apply and relocate_ops:
            warnings.extend(execute(relocate_ops, project_path))

    # Stages 2-4: FILE_NAMING (planned AFTER flatten + relocate)
    if "TEST_QUALITY_FILE_NAMING" in rules:
        splits, merges, renames = plan_naming(project_path)
        report.ops.extend(splits)
        report.ops.extend(merges)
        report.ops.extend(renames)
        if apply:
            warnings.extend(execute(splits, project_path))
            warnings.extend(execute(merges, project_path))
            warnings.extend(execute(renames, project_path))

    report.warnings = warnings

    report.unfixable = collect_unfixable(project_path)
    return report


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _fmt_target(t: Path | list[Path], root: Path) -> str:
    if isinstance(t, Path):
        try:
            return str(t.relative_to(root))
        except ValueError:
            return str(t)
    return ", ".join(_fmt_target(x, root) for x in t)


def format_report(r: PipelineReport, project_path: Path) -> str:
    lines: list[str] = []
    head = "applied" if r.applied else "dry-run"
    lines.append(f"\nPipeline ({head}) on {project_path}")
    lines.append("=" * 78)
    counts = r.by_kind()
    total = sum(counts.values())
    if not total:
        lines.append("  (no deterministic ops planned)")
    else:
        for kind in ("flatten", "relocate", "split", "merge", "rename"):
            n = counts.get(kind, 0)
            if n:
                lines.append(f"  Stage {kind.upper():9s} {n} op(s)")
    if r.ops:
        lines.append("")
        lines.append("Details (first 30):")
        for op in r.ops[:30]:
            try:
                src = op.source.relative_to(project_path)
            except ValueError:
                src = op.source
            lines.append(f"  [{op.kind:8s}] {src}")
            lines.append(f"               -> {_fmt_target(op.target, project_path)}")
            lines.append(f"               rationale: {op.rationale}")
        if len(r.ops) > 30:
            lines.append(f"  ... +{len(r.ops) - 30} more")
    lines.append("")
    if r.unfixable:
        lines.append(
            f"Out of pipeline (agent-driven, {len(r.unfixable)} finding(s)):"
        )
        for u in r.unfixable[:20]:
            tf = u.get("test_file") or u.get("path") or "?"
            lines.append(f"  {u['rule_id']}: {tf}")
        if len(r.unfixable) > 20:
            lines.append(f"  ... +{len(r.unfixable) - 20} more")
        lines.append(
            "  -> Run /scenario-rename or inspect manually — these tests "
            "may be legitimate or candidates for deletion."
        )
    else:
        lines.append("Out of pipeline: 0 finding")
    if r.warnings:
        lines.append("")
        lines.append(f"Warnings ({len(r.warnings)}):")
        for w in r.warnings[:15]:
            lines.append(f"  ! {w}")
        if len(r.warnings) > 15:
            lines.append(f"  ... +{len(r.warnings) - 15} more")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("project_path", type=Path, help="Path to package root")
    parser.add_argument(
        "--apply", action="store_true", help="Mutate the project (default: dry-run)"
    )
    parser.add_argument(
        "--rules",
        default="TEST_QUALITY_PYRAMID_LEVEL,TEST_QUALITY_FILE_NAMING",
        help="Comma-separated rule_ids to fix",
    )
    args = parser.parse_args()

    project_path: Path = args.project_path.resolve()
    if not project_path.exists():
        print(f"error: {project_path} does not exist", file=sys.stderr)
        return 2

    rules = {r.strip() for r in args.rules.split(",") if r.strip()}
    report = run(project_path, apply=args.apply, rules=rules)
    print(format_report(report, project_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
