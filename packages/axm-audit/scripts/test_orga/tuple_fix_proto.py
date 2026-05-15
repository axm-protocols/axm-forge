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
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from axm_audit.core.auditor import audit_project

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


OpKind = Literal["relocate", "split", "merge", "rename"]


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


def _check_by_rule(project_path: Path, rule_id: str) -> list[dict[str, Any]]:
    result = audit_project(project_path, category="test_quality")
    for check in result.checks:
        if getattr(check, "rule_id", "") == rule_id:
            return _findings(check)
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
    result = audit_project(project_path, category="test_quality")
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


def _execute_split(op: FileOp) -> None:
    raise NotImplementedError(
        "Stage SPLIT requires axm_anvil.move_symbols + a `split_map` from "
        "the FILE_NAMING finding routing each test to its target file. "
        "Wire executor in iteration 2."
    )


def _execute_merge(op: FileOp) -> None:
    raise NotImplementedError(
        "Stage COLLIDE merge requires axm_anvil.move_symbols (move every "
        "test_* from source to target, drop empty source). "
        "Wire executor in iteration 2."
    )


def execute(ops: list[FileOp]) -> None:
    for op in ops:
        if op.kind == "relocate":
            _execute_relocate(op)
        elif op.kind == "rename":
            _execute_rename(op)
        elif op.kind == "split":
            _execute_split(op)
        elif op.kind == "merge":
            _execute_merge(op)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def run(
    project_path: Path, *, apply: bool, rules: set[str]
) -> PipelineReport:
    report = PipelineReport(applied=apply)

    # Stage 1: RELOCATE
    if "TEST_QUALITY_PYRAMID_LEVEL" in rules:
        relocate_ops = plan_relocate(project_path)
        report.ops.extend(relocate_ops)
        if apply and relocate_ops:
            execute(relocate_ops)
            # Re-audit happens implicitly: stages 2-4 call audit_project again.

    # Stages 2-4: FILE_NAMING
    if "TEST_QUALITY_FILE_NAMING" in rules:
        splits, merges, renames = plan_naming(project_path)
        report.ops.extend(splits)
        report.ops.extend(merges)
        report.ops.extend(renames)
        if apply:
            execute(splits)
            execute(merges)
            execute(renames)

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
        for kind in ("relocate", "split", "merge", "rename"):
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
