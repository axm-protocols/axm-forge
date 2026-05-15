"""Prototype: deterministic test-suite auto-fixer.

Pipeline (4 stages, all deterministic; NO_PACKAGE_SYMBOL is rapported but
left to a human/agent — its verdict is context-dependent):

    1. RELOCATE   (PYRAMID_LEVEL mismatch)    git mv across tiers
    2. SPLIT      (FILE_NAMING SPLIT, ad-hoc) axm_anvil.move_symbols
    3. COLLIDE    (FILE_NAMING COLLIDE)       axm_anvil.move_symbols
    4. RENAME     (FILE_NAMING NAME_MISMATCH) git mv

Each stage is idempotent on its own; the chain re-audits the project
between stage 1 and stages 2-4 to ensure SPLIT/MERGE/RENAME act on
post-RELOCATE paths.

Companion to:
  * tuple_naming_proto.py       — integration tuple detector (v5, May 2026)
  * tuple_naming_e2e_proto.py   — e2e CLI tuple detector
  * README_E2E_SESSION.md       — context: what the rule should fix

Usage::

    uv run --python 3.12 python tuple_fix_proto.py /tmp/proto-fix/axm-audit-copy

The script defaults to --dry-run.  Pass --apply to actually mutate the
target.  --rules=... selects which stages run (comma-separated rule_ids).
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
from typing import Literal

# axm-audit reads the project; axm-anvil writes to it.
from axm_audit.core.auditor import audit_project

try:
    from axm_anvil.core.move import move_symbols
except ImportError:  # pragma: no cover
    move_symbols = None  # type: ignore[assignment]

NON_DETERMINISTIC_RULES = frozenset(
    {
        # NO_PACKAGE_SYMBOL: a test that exercises no package symbol may
        # be a legitimate formal check on an artefact (e.g. property
        # check on a generated manifest) or a candidate for deletion.
        # The verdict is context-dependent — use /scenario-rename or
        # inspect manually.
        "TEST_QUALITY_NO_PACKAGE_SYMBOL",
    }
)

TOP_K = 2


# ---------------------------------------------------------------------------
# Tuple detection — inlined from tuple_naming_proto + tuple_naming_e2e_proto
# (the production rule TEST_QUALITY_FILE_NAMING (AXM-1722) will move these
# helpers into axm_audit._shared; the proto inlines what it needs).
# ---------------------------------------------------------------------------


def to_snake(name: str) -> str:
    if not name:
        return name
    name = name.replace("-", "_")
    out: list[str] = []
    for i, ch in enumerate(name):
        if (
            ch.isupper()
            and i > 0
            and (name[i - 1].islower() or (i + 1 < len(name) and name[i + 1].islower()))
        ):
            out.append("_")
        out.append(ch.lower())
    return "".join(out).lstrip("_")


def _collect_package_imports(tree: ast.AST, pkg: str) -> set[str]:
    """{local_name} for every import from PACKAGE (any depth)."""
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == pkg or mod.startswith(pkg + "."):
                for alias in node.names:
                    imports.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == pkg or alias.name.startswith(pkg + "."):
                    imports.add(alias.asname or alias.name.split(".")[0])
    return imports


def _used_in_node(node: ast.AST, known: set[str]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id in known:
            counter[sub.id] += 1
        elif isinstance(sub, ast.Attribute):
            root = sub
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id in known:
                counter[root.id] += 1
    return counter


def _walk_test_funcs(tree: ast.Module) -> list[ast.FunctionDef]:
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


def _load_project_scripts(pkg_root: Path) -> set[str]:
    pyproject = pkg_root / "pyproject.toml"
    if not pyproject.exists():
        return set()
    data = tomllib.loads(pyproject.read_text())
    scripts = data.get("project", {}).get("scripts", {})
    return set(scripts.keys()) if isinstance(scripts, dict) else set()


def _argv_from_subprocess_call(call: ast.Call) -> list[str | None] | None:
    """Resolve argv of a subprocess.* call to list[str | None].

    Returns None if not a subprocess call or argv unresolvable as a list literal.
    """
    func = call.func
    if not (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "subprocess"
        and func.attr in {"run", "call", "check_call", "check_output", "Popen"}
    ):
        return None
    for kw in call.keywords:
        if (
            kw.arg == "shell"
            and isinstance(kw.value, ast.Constant)
            and kw.value.value is True
        ):
            return None
    if not call.args:
        return None
    first = call.args[0]
    if not isinstance(first, ast.List):
        return None
    out: list[str | None] = []
    for el in first.elts:
        if isinstance(el, ast.Constant) and isinstance(el.value, str):
            out.append(el.value)
        else:
            out.append(None)
    return out


def _cli_tuple_from_call(call: ast.Call, scripts: set[str]) -> tuple[str, str] | None:
    argv = _argv_from_subprocess_call(call)
    if argv is None:
        return None
    script_modules = {s.replace("-", "_"): s for s in scripts}
    for i, tok in enumerate(argv):
        if tok is None:
            continue
        match_script: str | None = None
        if tok in scripts:
            match_script = tok
        elif tok in script_modules:
            match_script = script_modules[tok]
        if match_script is None:
            continue
        sub = ""
        if (
            i + 1 < len(argv)
            and argv[i + 1] is not None
            and not argv[i + 1].startswith("-")  # type: ignore[union-attr]
        ):
            sub = argv[i + 1]  # type: ignore[assignment]
        return (match_script, sub)
    return None


def _canonical_filename(
    tokens: list[str], tier: Literal["integration", "e2e"], single_binary: str | None
) -> str:
    """Emit canonical `test_<a>-<b>.py` from a list of tuple-labels.

    For e2e with single_binary set, strip the binary prefix.
    """
    if not tokens:
        return "test_UNKNOWN.py"
    parts = list(tokens)
    if tier == "e2e" and single_binary is not None:
        prefix = single_binary + "-"
        parts = [
            p[len(prefix) :]
            if p.startswith(prefix)
            else ("" if p == single_binary else p)
            for p in parts
        ]
        parts = [p for p in parts if p]
        if not parts:
            parts = [to_snake(single_binary)]
    return "test_" + "-".join(to_snake(s) for s in parts) + ".py"


def _file_tuple(
    tree: ast.Module, tier: str, pkg: str, scripts: set[str]
) -> tuple[tuple[str, ...], list[tuple[str, ...]]]:
    """Compute the file's union top-K tuple AND per-test top-K tuples.

    Returns (union_topk, per_test_topk).  SPLIT iff len({per_test...}) > 1.
    """
    per_test: list[tuple[str, ...]] = []
    agg: Counter[str] = Counter()
    if tier == "integration":
        known = _collect_package_imports(tree, pkg)
        for f in _walk_test_funcs(tree):
            used = _used_in_node(f, known)
            ranked = [s for s, _ in used.most_common()]
            per_test.append(tuple(sorted(ranked[:TOP_K])))
            agg.update(used)
    elif tier == "e2e":
        # Crude: walk every Call site in test funcs, extract (bin, sub)
        for f in _walk_test_funcs(tree):
            local: Counter[str] = Counter()
            for sub_node in ast.walk(f):
                if isinstance(sub_node, ast.Call):
                    inv = _cli_tuple_from_call(sub_node, scripts)
                    if inv is not None:
                        label = inv[0] if not inv[1] else f"{inv[0]}-{inv[1]}"
                        local[label] += 1
                        agg[label] += 1
            ranked = [s for s, _ in local.most_common()]
            per_test.append(tuple(sorted(ranked[:TOP_K])))
    union = tuple(sorted([s for s, _ in agg.most_common()][:TOP_K]))
    return union, per_test


# ---------------------------------------------------------------------------
# FileOp model
# ---------------------------------------------------------------------------


@dataclass
class FileOp:
    kind: Literal["relocate", "split", "merge", "rename"]
    source: Path
    target: Path | list[Path]
    rationale: str
    source_rule: str
    symbols: list[str] | None = None  # for split: which test_* go to target


@dataclass
class PipelineReport:
    ops: list[FileOp] = field(default_factory=list)
    unfixable: list[dict] = field(default_factory=list)
    applied: bool = False

    def by_kind(self) -> dict[str, int]:
        counts: Counter[str] = Counter()
        for op in self.ops:
            counts[op.kind] += 1
        return dict(counts)


# ---------------------------------------------------------------------------
# Stage planners
# ---------------------------------------------------------------------------


def plan_relocate(project_path: Path) -> list[FileOp]:
    """Stage 1: PYRAMID_LEVEL mismatches → git mv across tiers.

    Aggregates per-file: a file is moved iff ALL its tests classify to the
    same target level different from current. Mixed-level files are skipped
    (require human split).
    """
    result = audit_project(project_path, category="test_quality")
    ops: list[FileOp] = []
    for check in result.checks:
        if type(check).__name__ != "PyramidCheckResult":
            continue
        per_file: dict[Path, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        per_file_cur: dict[Path, str] = {}
        for f in check.findings or []:
            d = f.model_dump() if hasattr(f, "model_dump") else f
            cur, lvl = d.get("current_level"), d.get("level")
            if cur == lvl:
                continue
            p = Path(d["path"])
            per_file[p][lvl] += 1
            per_file_cur[p] = cur
        for p, target_levels in per_file.items():
            if len(target_levels) != 1:
                # mixed-level mismatch in same file → not auto-fixable
                continue
            target_lvl = next(iter(target_levels))
            cur = per_file_cur[p]
            target = _retier(p, project_path, cur, target_lvl)
            ops.append(
                FileOp(
                    kind="relocate",
                    source=p,
                    target=target,
                    rationale=f"all {target_levels[target_lvl]} test(s) classify as {target_lvl}",
                    source_rule="TEST_QUALITY_PYRAMID_LEVEL",
                )
            )
    return ops


def _retier(p: Path, root: Path, cur: str, target_lvl: str) -> Path:
    """Compute the path under tests/{target_lvl}/ that mirrors p."""
    rel = p.relative_to(root)
    parts = list(rel.parts)
    # tests/<cur>/...rest...  →  tests/<target>/...rest...
    if parts[0] == "tests" and parts[1] == cur:
        parts[1] = target_lvl
    return root / Path(*parts)


def plan_naming(
    project_path: Path, pkg_name: str
) -> tuple[list[FileOp], list[FileOp], list[FileOp]]:
    """Stages 2-4: SPLIT, COLLIDE merge, NAME_MISMATCH rename.

    Returns (split_ops, merge_ops, rename_ops) in stage order.

    The proto computes tuples ad-hoc (TEST_QUALITY_FILE_NAMING isn't merged
    yet); once it is, this becomes `audit(..., category="test_quality")`
    consumption like plan_relocate.
    """
    scripts = _load_project_scripts(project_path)
    single_binary = next(iter(scripts)) if len(scripts) == 1 else None
    splits: list[FileOp] = []
    renames: list[FileOp] = []
    by_canonical: dict[tuple[str, str], list[Path]] = defaultdict(list)  # (tier, name)

    for tier in ("integration", "e2e"):
        tests_dir = project_path / "tests" / tier
        if not tests_dir.exists():
            continue
        for test_file in sorted(tests_dir.rglob("test_*.py")):
            if "__pycache__" in test_file.parts:
                continue
            try:
                tree = ast.parse(test_file.read_text())
            except SyntaxError:
                continue
            union, per_test = _file_tuple(tree, tier, pkg_name, scripts)
            if not union:
                continue  # NO_PACKAGE_SYMBOL territory — out of pipeline
            canonical = _canonical_filename(list(union), tier, single_binary)
            by_canonical[(tier, canonical)].append(test_file)

            # SPLIT: ≥2 distinct non-empty per_test tuples
            distinct = {t for t in per_test if t}
            if len(distinct) >= 2:
                suggested = [
                    _canonical_filename(list(t), tier, single_binary)
                    for t in sorted(distinct)
                ]
                splits.append(
                    FileOp(
                        kind="split",
                        source=test_file,
                        target=[test_file.parent / s for s in suggested],
                        rationale=f"{len(distinct)} distinct tuples in same file",
                        source_rule="TEST_QUALITY_FILE_NAMING",
                    )
                )
                continue  # if SPLIT, rename is irrelevant (children get good names)

            # NAME_MISMATCH: file basename ≠ canonical
            if test_file.name != canonical:
                renames.append(
                    FileOp(
                        kind="rename",
                        source=test_file,
                        target=test_file.parent / canonical,
                        rationale=f"current={test_file.name} canonical={canonical}",
                        source_rule="TEST_QUALITY_FILE_NAMING",
                    )
                )

    # COLLIDE: same canonical name for ≥2 files in same tier
    merges: list[FileOp] = []
    for (tier, canonical), files in by_canonical.items():
        if len(files) < 2:
            continue
        # Merge into the lexically-first file by convention; rest go away
        anchor = sorted(files)[0]
        for other in sorted(files)[1:]:
            merges.append(
                FileOp(
                    kind="merge",
                    source=other,
                    target=anchor,
                    rationale=f"COLLIDE on {canonical} in tests/{tier}/",
                    source_rule="TEST_QUALITY_FILE_NAMING",
                )
            )
    return splits, merges, renames


def collect_unfixable(project_path: Path) -> list[dict]:
    result = audit_project(project_path, category="test_quality")
    out: list[dict] = []
    for check in result.checks:
        rid = getattr(check, "rule_id", "")
        if rid not in NON_DETERMINISTIC_RULES:
            continue
        for f in check.findings or []:
            d = f.model_dump() if hasattr(f, "model_dump") else f
            out.append({"rule_id": rid, **d})
    return out


# ---------------------------------------------------------------------------
# Stage executors
# ---------------------------------------------------------------------------


def _execute_relocate(op: FileOp) -> None:
    assert isinstance(op.target, Path)
    op.target.parent.mkdir(parents=True, exist_ok=True)
    # git mv preserves history; fall back to plain rename if not under git.
    rc = subprocess.run(
        ["git", "mv", str(op.source), str(op.target)],
        cwd=str(op.source.parent),
        capture_output=True,
        text=True,
    )
    if rc.returncode != 0:
        shutil.move(str(op.source), str(op.target))


def _execute_rename(op: FileOp) -> None:
    _execute_relocate(op)  # same semantics


def _execute_split(op: FileOp) -> None:
    raise NotImplementedError(
        "Stage SPLIT requires axm_anvil.move_symbols + per-test routing logic. "
        "Validate the planner first; wire executor in iteration 2."
    )


def _execute_merge(op: FileOp) -> None:
    raise NotImplementedError(
        "Stage COLLIDE merge requires axm_anvil.move_symbols. "
        "Validate the planner first; wire executor in iteration 2."
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
    project_path: Path,
    pkg_name: str,
    *,
    apply: bool,
    rules: set[str],
) -> PipelineReport:
    report = PipelineReport(applied=apply)

    # Stage 1: RELOCATE
    if "TEST_QUALITY_PYRAMID_LEVEL" in rules:
        ops = plan_relocate(project_path)
        report.ops.extend(ops)
        if apply and ops:
            execute(ops)

    # Re-audit after stage 1 — paths have changed
    # (skipped if no relocate happened)

    # Stages 2-4: SPLIT, MERGE, RENAME
    if "TEST_QUALITY_FILE_NAMING" in rules:
        splits, merges, renames = plan_naming(project_path, pkg_name)
        # Order: split first (creates new files), merge next (collapses),
        # rename last (cosmetic).
        report.ops.extend(splits)
        report.ops.extend(merges)
        report.ops.extend(renames)
        if apply:
            execute(splits)
            execute(merges)
            execute(renames)

    # Report (always) — UNKNOWNs are out-of-pipeline
    report.unfixable = collect_unfixable(project_path)
    return report


# ---------------------------------------------------------------------------
# CLI / reporting
# ---------------------------------------------------------------------------


def format_report(r: PipelineReport, project_path: Path) -> str:
    lines = []
    lines.append(
        f"\nPipeline ({'applied' if r.applied else 'dry-run'}) on {project_path}"
    )
    lines.append("=" * 78)
    counts = r.by_kind()
    if not r.ops:
        lines.append("  (no deterministic ops planned)")
    else:
        for kind in ("relocate", "split", "merge", "rename"):
            n = counts.get(kind, 0)
            if n:
                lines.append(f"  Stage {kind.upper():9s} {n} op(s)")
        lines.append("")
        lines.append("Details:")
        for op in r.ops:
            tgt = (
                op.target.relative_to(project_path)
                if isinstance(op.target, Path)
                else [t.relative_to(project_path) for t in op.target]
            )
            src = op.source.relative_to(project_path)
            lines.append(f"  [{op.kind:8s}] {src}")
            lines.append(f"               -> {tgt}")
            lines.append(f"               rationale: {op.rationale}")
    lines.append("")
    if r.unfixable:
        lines.append(f"Out of pipeline (agent-driven, {len(r.unfixable)} finding(s)):")
        for u in r.unfixable:
            tf = u.get("test_file") or u.get("path") or "?"
            lines.append(f"  {u['rule_id']}: {tf}")
        lines.append(
            "  Run /scenario-rename or inspect manually — these tests "
            "may be legitimate or candidates for deletion."
        )
    else:
        lines.append("Out of pipeline: 0 finding")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic test-suite fixer (proto)"
    )
    parser.add_argument("project_path", type=Path, help="Path to package root")
    parser.add_argument(
        "--apply", action="store_true", help="Mutate the project (default: dry-run)"
    )
    parser.add_argument(
        "--rules",
        default="TEST_QUALITY_PYRAMID_LEVEL,TEST_QUALITY_FILE_NAMING",
        help="Comma-separated rule_ids to fix",
    )
    parser.add_argument(
        "--pkg-name",
        default=None,
        help="Python package name (e.g. axm_audit). Defaults to <project_path>/pyproject project.name.",
    )
    args = parser.parse_args()

    project_path: Path = args.project_path.resolve()
    if not project_path.exists():
        print(f"error: {project_path} does not exist", file=sys.stderr)
        return 2

    pkg_name = args.pkg_name
    if pkg_name is None:
        pyproject = project_path / "pyproject.toml"
        if pyproject.exists():
            data = tomllib.loads(pyproject.read_text())
            name = data.get("project", {}).get("name", "")
            pkg_name = name.replace("-", "_")
    if not pkg_name:
        print("error: could not infer --pkg-name", file=sys.stderr)
        return 2

    rules = {r.strip() for r in args.rules.split(",") if r.strip()}
    report = run(project_path, pkg_name, apply=args.apply, rules=rules)
    print(format_report(report, project_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
