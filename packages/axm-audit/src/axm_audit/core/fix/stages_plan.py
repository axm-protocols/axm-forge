"""Stage planners: read findings, emit ``FileOp`` lists (no mutation).

Three planners — ``plan_flatten`` (Stage 0), ``plan_relocate`` (Stage 1),
``plan_naming`` (Stages 2-4) — each consumes audit findings and returns a
list of ``FileOp`` describing what the corresponding executor in
``stages_execute`` will do. Pure functions over the current disk state.
"""

from __future__ import annotations

import ast
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .findings import (
    _check_by_rule,
    _class_needs_flatten,
    _load_project_scripts,
    get_pkg_prefixes,
)
from .models import FileOp
from .paths import _retier, _safe_filename, _tier_for_path
from .tests_ast import (
    _class_is_pathological,
    _file_has_pathological_class,
    _top_level_test_classes,
)

__all__ = ["plan_flatten", "plan_naming", "plan_relocate"]

_FLATTEN_VERDICTS = {"SPLIT", "COLLIDE", "NAME_MISMATCH"}


@dataclass(frozen=True)
class _FlattenCtx:
    tier: str
    pkg_prefixes: tuple[str, ...]
    scripts: dict[str, str]
    single_binary: str | None


def _add_existing_abs(target: set[Path], raw: str) -> None:
    p = Path(raw)
    if p.is_absolute() and p.exists():
        target.add(p)


def _collect_flatten_candidates(findings: list[dict[str, Any]]) -> set[Path]:
    candidates: set[Path] = set()
    for d in findings:
        if d.get("verdict") not in _FLATTEN_VERDICTS:
            continue
        path_raw = d.get("path", "")
        p = Path(path_raw)
        if p.is_absolute() and p.exists():
            candidates.add(p)
            continue
        for fp in d.get("files") or ():
            _add_existing_abs(candidates, fp)
    return candidates


def _classify_classes(
    tree: ast.AST, ctx: _FlattenCtx
) -> tuple[list[str], list[tuple[str, str]]]:
    to_flatten: list[str] = []
    pathological: list[tuple[str, str]] = []
    for cls in _top_level_test_classes(tree):
        if not _class_needs_flatten(
            cls,
            tree,
            tier=ctx.tier,
            pkg_prefixes=ctx.pkg_prefixes,
            scripts=ctx.scripts,
            single_binary=ctx.single_binary,
        ):
            continue
        reason = _class_is_pathological(cls)
        if reason is not None:
            pathological.append((cls.name, reason))
        else:
            to_flatten.append(cls.name)
    return to_flatten, pathological


def _emit_flatten_ops(
    src: Path,
    to_flatten: list[str],
    pathological: list[tuple[str, str]],
) -> list[FileOp]:
    ops: list[FileOp] = []
    if to_flatten:
        ops.append(
            FileOp(
                kind="flatten",
                source=src,
                target=src,
                rationale=(
                    f"flatten {len(to_flatten)} heterogeneous class(es): {to_flatten}"
                ),
                source_rule="TEST_QUALITY_FILE_NAMING",
                split_map={c: [] for c in to_flatten},
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


def plan_flatten(project_path: Path) -> list[FileOp]:
    """Stage 0: detect Test* classes with divergent method tuples → flatten.

    A class whose methods don't all share the same canonical tuple is not
    a movable unit. We flatten it to top-level functions so SPLIT can
    route each method to its correct target file. Pathological classes
    (using ``self.x``, inheriting non-object, having __init__) cannot be
    flattened deterministically and emit an out-of-pipeline warning.
    """
    findings = _check_by_rule(project_path, "TEST_QUALITY_FILE_NAMING")
    pkg_prefixes = get_pkg_prefixes(project_path)
    scripts = _load_project_scripts(project_path)
    single_binary = next(iter(scripts)) if len(scripts) == 1 else None
    ops: list[FileOp] = []
    for src in sorted(_collect_flatten_candidates(findings)):
        tier_str = _tier_for_path(src)
        if tier_str not in ("integration", "e2e"):
            continue
        ctx = _FlattenCtx(
            tier=tier_str,
            pkg_prefixes=pkg_prefixes,
            scripts=scripts,
            single_binary=single_binary,
        )
        tree = ast.parse(src.read_text())
        to_flatten, pathological = _classify_classes(tree, ctx)
        ops.extend(_emit_flatten_ops(src, to_flatten, pathological))
    return ops


def plan_relocate(project_path: Path) -> list[FileOp]:
    """Aggregate PYRAMID_LEVEL findings → 1 op per *unanimous* file.

    A file is relocated only when **every** test in it agrees on a single
    target level distinct from the current tier. If at least one test is
    already correctly tiered (``cur == lvl``), or tests disagree on the
    target, the file is mixed and the proto leaves it alone — manual
    SPLIT / `/scenario-rename` is the correct response.

    Why unanimity matters (B3 oscillation, May 2026): the PYRAMID_LEVEL
    rule is per-test, so a file like
    ``tests/integration/test_X.py`` containing one ``real I/O +
    public import`` test (correct here) and one ``no I/O`` test (would
    classify as unit) used to be relocated to ``tests/unit/`` based on
    the single mismatch — then on the next iteration the kept ``real I/O``
    test would flag the file in ``tests/unit/`` as needing relocation
    back to ``integration``, oscillating forever. Requiring unanimity
    breaks the cycle: such files are out of pipeline until split.
    """
    findings = _check_by_rule(project_path, "TEST_QUALITY_PYRAMID_LEVEL")
    per_file: dict[Path, Counter[str]] = defaultdict(Counter)
    for d in findings:
        lvl = d.get("level")
        if lvl is None:
            continue
        per_file[Path(d["path"])][lvl] += 1
    ops: list[FileOp] = []
    for p, target_levels in per_file.items():
        if len(target_levels) != 1:
            continue  # mixed; needs manual split
        target_lvl = next(iter(target_levels))
        cur_tier = _tier_for_path(p)
        if cur_tier == target_lvl:
            continue  # already correct
        n = target_levels[target_lvl]
        ops.append(
            FileOp(
                kind="relocate",
                source=p,
                target=_retier(p, project_path, target_lvl),
                rationale=f"{n} test(s) unanimously classify as {target_lvl}",
                source_rule="TEST_QUALITY_PYRAMID_LEVEL",
            )
        )
    return ops


def _is_canonical_tier(p: Path) -> bool:
    return _tier_for_path(p) in ("integration", "e2e")


def _split_op_from_finding(d: dict[str, Any], src: Path) -> FileOp:
    suggested = d.get("suggested_splits") or [d.get("proposed_name", "")]
    suggested = [_safe_filename(s) for s in suggested if s]
    suggested = [s for s in suggested if s != "test_UNKNOWN.py"]
    targets = [src.parent / s for s in suggested]
    return FileOp(
        kind="split",
        source=src,
        target=targets,
        rationale=f"{len(targets)} distinct tuples",
        source_rule="TEST_QUALITY_FILE_NAMING",
        split_map=d.get("split_map"),
    )


def _plan_splits(findings: list[dict[str, Any]], consumed: set[Path]) -> list[FileOp]:
    splits: list[FileOp] = []
    for d in findings:
        src = Path(d["path"])
        if not _is_canonical_tier(src):
            continue
        if src.exists() and _file_has_pathological_class(src):
            continue
        consumed.add(src)
        splits.append(_split_op_from_finding(d, src))
    return splits


def _merge_ops_from_finding(
    d: dict[str, Any], files: list[Path], consumed: set[Path]
) -> list[FileOp]:
    anchor = files[0]
    rationale = (
        f"COLLIDE on {d.get('canonical_name', '?')} in tests/{d.get('tier', '?')}/"
    )
    ops: list[FileOp] = []
    for other in files[1:]:
        consumed.add(other)
        ops.append(
            FileOp(
                kind="merge",
                source=other,
                target=anchor,
                rationale=rationale,
                source_rule="TEST_QUALITY_FILE_NAMING",
            )
        )
    return ops


def _plan_merges(findings: list[dict[str, Any]], consumed: set[Path]) -> list[FileOp]:
    merges: list[FileOp] = []
    for d in findings:
        files = sorted(Path(p) for p in d.get("files", []))
        if len(files) < 2:
            continue
        if not all(_is_canonical_tier(f) for f in files):
            continue
        merges.extend(_merge_ops_from_finding(d, files, consumed))
    return merges


def _plan_renames(findings: list[dict[str, Any]], consumed: set[Path]) -> list[FileOp]:
    renames: list[FileOp] = []
    for d in findings:
        src = Path(d["path"])
        if src in consumed or not _is_canonical_tier(src):
            continue
        proposed = _safe_filename(d.get("proposed_name", ""))
        if not proposed or src.name == proposed or proposed == "test_UNKNOWN.py":
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
    return renames


def plan_naming(
    project_path: Path,
) -> tuple[list[FileOp], list[FileOp], list[FileOp]]:
    """Read FILE_NAMING findings → (splits, merges, renames).

    Returns the three stages in *execution* order.  Each stage is mutually
    exclusive on a given file: a SPLIT victim doesn't get a RENAME (its
    children inherit canonical names from the split), and a COLLIDE victim
    doesn't get a RENAME (the merge target already has the canonical name).
    """
    findings = _check_by_rule(project_path, "TEST_QUALITY_FILE_NAMING")
    by_verdict: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for d in findings:
        by_verdict[d.get("verdict", "")].append(d)

    consumed: set[Path] = set()
    splits = _plan_splits(by_verdict.get("SPLIT", []), consumed)
    merges = _plan_merges(by_verdict.get("COLLIDE", []), consumed)
    renames = _plan_renames(by_verdict.get("NAME_MISMATCH", []), consumed)
    return splits, merges, renames
