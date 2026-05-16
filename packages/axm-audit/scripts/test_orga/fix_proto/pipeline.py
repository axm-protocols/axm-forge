"""Top-level orchestration: ``run`` + the fixed-point iteration loop.

The fixed-point loop (``MAX_ITERATIONS=6``) is the B3 fix: the cascade
of RELOCATE → SPLIT → MERGE → RENAME mutates classification (a moved
test may switch tier; a SPLIT can expose a new NAME_MISMATCH that
wasn't visible pre-split). Re-running the stages until convergence
gives a chance to settle to zero — see ``README_FIX_PROTO.md`` for the
caveats discovered during pass 12.

Post-loop polish: extract duplicated helpers + run ruff format/fix.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .cst_rewrite import _invalidate_import_index
from .extract_helpers import _extract_shared_helpers
from .findings import collect_unfixable
from .layout_and_move import (
    flatten_tier_layout,
    relocate_non_canonical_tiers,
)
from .models import MAX_ITERATIONS, PipelineReport
from .stages_execute import execute
from .stages_plan import plan_flatten, plan_naming, plan_relocate

__all__ = ["run", "MAX_ITERATIONS"]


def _run_one_iteration(
    project_path: Path,
    *,
    apply: bool,
    rules: set[str],
    report: PipelineReport,
    warnings: list[str],
) -> int:
    """Execute one full pass of the pipeline; return number of ops emitted.

    Returns 0 when nothing remained to fix this iteration (convergence
    signal for the outer loop). ops + warnings accumulate into the
    caller-owned report/warnings list across iterations.
    """
    iter_ops = 0

    # Stage 0.5: relocate non-canonical tier dirs (tests/functional/, ...)
    # into tests/integration/ so the rest of the pipeline sees only
    # canonical tier paths. Stage 1 RELOCATE will then re-tier each file
    # to its correct pyramid level based on PYRAMID_LEVEL findings.
    if apply and "TEST_QUALITY_PYRAMID_LEVEL" in rules:
        non_canon_msgs = relocate_non_canonical_tiers(project_path)
        if non_canon_msgs:
            warnings.extend(non_canon_msgs)
            iter_ops += len(non_canon_msgs)
            _invalidate_import_index(project_path)

    # Stage 0: FLATTEN heterogeneous Test* classes (FILE_NAMING preflight).
    # Done first so RELOCATE / SPLIT / MERGE / RENAME see top-level units only.
    if "TEST_QUALITY_FILE_NAMING" in rules:
        flatten_ops = plan_flatten(project_path)
        # Don't count pathological flatten ops as "work emitted" — they
        # only emit a warning and re-fire every iteration, breaking
        # convergence. They are surfaced via collect_unfixable instead.
        actionable_flatten = [
            op for op in flatten_ops
            if not op.rationale.startswith("PATHOLOGICAL")
        ]
        report.ops.extend(actionable_flatten)
        if apply and actionable_flatten:
            warnings.extend(execute(actionable_flatten, project_path))
            _invalidate_import_index(project_path)
            iter_ops += len(actionable_flatten)

    # Stage 1: RELOCATE
    if "TEST_QUALITY_PYRAMID_LEVEL" in rules:
        relocate_ops = plan_relocate(project_path)
        report.ops.extend(relocate_ops)
        if apply and relocate_ops:
            warnings.extend(execute(relocate_ops, project_path))
            _invalidate_import_index(project_path)
            iter_ops += len(relocate_ops)

    # Stage 1.5: FLATTEN_LAYOUT.
    if apply and "TEST_QUALITY_PYRAMID_LEVEL" in rules:
        flatten_msgs = flatten_tier_layout(project_path)
        if flatten_msgs:
            warnings.extend(flatten_msgs)
            iter_ops += len(flatten_msgs)
            _invalidate_import_index(project_path)

    # Stages 2-4: FILE_NAMING (planned AFTER flatten + relocate).
    if "TEST_QUALITY_FILE_NAMING" in rules:
        if apply:
            splits, _, _ = plan_naming(project_path)
            report.ops.extend(splits)
            if splits:
                warnings.extend(execute(splits, project_path))
                _invalidate_import_index(project_path)
                iter_ops += len(splits)
            _, merges, _ = plan_naming(project_path)  # re-plan post-SPLIT
            report.ops.extend(merges)
            if merges:
                warnings.extend(execute(merges, project_path))
                _invalidate_import_index(project_path)
                iter_ops += len(merges)
            _, _, renames = plan_naming(project_path)  # re-plan post-MERGE
            report.ops.extend(renames)
            if renames:
                warnings.extend(execute(renames, project_path))
                iter_ops += len(renames)
        else:
            splits, merges, renames = plan_naming(project_path)
            report.ops.extend(splits)
            report.ops.extend(merges)
            report.ops.extend(renames)
            iter_ops += len(splits) + len(merges) + len(renames)
    return iter_ops


def run(
    project_path: Path, *, apply: bool, rules: set[str]
) -> PipelineReport:
    report = PipelineReport(applied=apply)

    warnings: list[str] = []

    # B3 fixed-point loop. The cascade of RELOCATE → SPLIT → MERGE →
    # RENAME mutates classification: a test moved across tiers may
    # change its `current_level` (integration tests with no I/O become
    # unit after RELOCATE), a SPLIT may free a NAME_MISMATCH that only
    # appeared because the audit saw the pre-split tuple. Re-iterate
    # until either nothing new is planned or we hit the iteration cap.
    # In dry-run mode we only need one pass (no mutation).
    if apply:
        for i in range(MAX_ITERATIONS):
            report.iterations = i + 1
            iter_ops = _run_one_iteration(
                project_path,
                apply=True, rules=rules, report=report, warnings=warnings,
            )
            if iter_ops == 0:
                break
    else:
        _run_one_iteration(
            project_path,
            apply=False, rules=rules, report=report, warnings=warnings,
        )
        report.iterations = 1

    # Post-pipeline polish: extract shared helpers, then ruff fix + format.
    if apply:
        extraction_msgs = _extract_shared_helpers(project_path)
        warnings.extend(extraction_msgs)
        extracted_names = {
            m.split("`")[1] for m in extraction_msgs
            if (
                m.startswith("extracted helper `")
                or m.startswith("extracted fixture `")
            )
            and "`" in m
        }
        if extracted_names:
            warnings = [
                w for w in warnings
                if not (
                    "duplicated in target" in w
                    and any(f"Helper '{n}'" in w for n in extracted_names)
                )
            ]
        warnings.extend(_ruff_format_tests(project_path))

    report.warnings = warnings
    report.unfixable = collect_unfixable(project_path)
    return report


def _ruff_format_tests(project_path: Path) -> list[str]:
    """Run ``ruff format`` and ``ruff check --fix-only`` on ``tests/``.

    Idempotent. ``format`` resolves E501 + UP034; ``check --fix-only``
    with safe fixes resolves F401 (unused imports the proto over-copied
    despite Fix 1, e.g. in edge cases) + I001 (import order).

    Failures are caught and turned into warnings — we never want this
    polish step to abort an otherwise-successful apply.
    """
    tests = project_path / "tests"
    if not tests.exists():
        return []
    msgs: list[str] = []
    for cmd_args, label in (
        (
            [
                "ruff", "check", "--fix-only",
                "--select", "F401,I001,UP034",
                str(tests),
            ],
            "ruff --fix F401/I001/UP034",
        ),
        (["ruff", "format", str(tests)], "ruff format"),
    ):
        try:
            rc = subprocess.run(
                cmd_args, capture_output=True, text=True, cwd=project_path
            )
        except FileNotFoundError:
            msgs.append(f"{label} skipped: ruff not on PATH")
            return msgs
        if rc.returncode not in (0, 1):
            msgs.append(
                f"{label} returned exit {rc.returncode}: {rc.stderr[:200]}"
            )
    return msgs
