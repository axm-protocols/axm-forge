"""Stage planners: read findings, emit ``FileOp`` lists (no mutation).

Three planners — ``plan_flatten`` (Stage 0), ``plan_relocate`` (Stage 1),
``plan_naming`` (Stages 2-4) — each consumes audit findings and returns a
list of ``FileOp`` describing what the corresponding executor in
``stages_execute`` will do. Pure functions over the current disk state.
"""

from __future__ import annotations

import ast
from collections import Counter, defaultdict
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
        tier_str = _tier_for_path(src)
        if tier_str not in ("integration", "e2e"):
            continue
        tree = ast.parse(src.read_text())
        classes_to_flatten: list[str] = []
        pathological: list[tuple[str, str]] = []
        for cls in _top_level_test_classes(tree):
            if not _class_needs_flatten(
                cls,
                tree,
                tier=tier_str,
                pkg_prefixes=pkg_prefixes,
                scripts=scripts,
                single_binary=single_binary,
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
    splits: list[FileOp] = []
    merges: list[FileOp] = []
    renames: list[FileOp] = []

    by_verdict: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for d in findings:
        by_verdict[d.get("verdict", "")].append(d)

    consumed: set[Path] = set()

    # 2. SPLIT
    for d in by_verdict.get("SPLIT", []):
        src = Path(d["path"])
        # B2 defensive: SPLIT executor refuses anything outside
        # tests/integration|e2e. Filter at plan time so the report
        # doesn't surface ops that will silently skip.
        if _tier_for_path(src) not in ("integration", "e2e"):
            continue
        # B1 defensive: SPLIT cannot proceed when the file still has a
        # pathological Test* class (Stage 0 was unable to flatten it).
        # Skip — collect_unfixable surfaces these as unfixable.
        if src.exists() and _file_has_pathological_class(src):
            continue
        consumed.add(src)
        suggested = d.get("suggested_splits") or [d.get("proposed_name", "")]
        suggested = [_safe_filename(s) for s in suggested if s]
        suggested = [s for s in suggested if s != "test_UNKNOWN.py"]
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
        # B2 defensive: MERGE relies on anvil moves which operate within
        # a canonical tier. Drop collisions that include non-canonical paths.
        if any(_tier_for_path(f) not in ("integration", "e2e") for f in files):
            continue
        anchor = files[0]
        for other in files[1:]:
            consumed.add(other)
            merges.append(
                FileOp(
                    kind="merge",
                    source=other,
                    target=anchor,
                    rationale=(
                        f"COLLIDE on {d.get('canonical_name', '?')} "
                        f"in tests/{d.get('tier', '?')}/"
                    ),
                    source_rule="TEST_QUALITY_FILE_NAMING",
                )
            )

    # 4. RENAME — skip files consumed by stages 2/3
    for d in by_verdict.get("NAME_MISMATCH", []):
        src = Path(d["path"])
        if src in consumed:
            continue
        # B2 defensive: a non-canonical-tier file should be relocated by
        # Stage 0.5, not renamed in place. Skip — next iteration will see
        # it under its canonical tier.
        if _tier_for_path(src) not in ("integration", "e2e"):
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

    return splits, merges, renames
