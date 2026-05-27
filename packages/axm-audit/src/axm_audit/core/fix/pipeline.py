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
from collections.abc import Callable
from pathlib import Path

from .cst_rewrite import invalidate_import_index
from .extract_helpers import _extract_shared_helpers
from .findings import collect_unfixable
from .layout_and_move import (
    flatten_tier_layout,
    relocate_non_canonical_tiers,
)
from .models import MAX_ITERATIONS, PipelineReport
from .stages_execute import execute
from .stages_plan import plan_flatten, plan_naming, plan_relocate

__all__ = ["DEFAULT_RULES", "MAX_ITERATIONS", "run"]

DEFAULT_RULES: frozenset[str] = frozenset(
    {"TEST_QUALITY_PYRAMID_LEVEL", "TEST_QUALITY_FILE_NAMING"}
)


def _apply_warning_stage(
    project_path: Path,
    producer: Callable[[Path], list[str]],
    warnings: list[str],
) -> int:
    msgs = producer(project_path)
    if not msgs:
        return 0
    warnings.extend(msgs)
    invalidate_import_index(project_path)
    return len(msgs)


def _apply_ops_stage(
    project_path: Path,
    ops: list,
    report: PipelineReport,
    warnings: list[str],
    *,
    invalidate: bool = True,
) -> int:
    report.ops.extend(ops)
    if not ops:
        return 0
    warnings.extend(execute(ops, project_path))
    if invalidate:
        invalidate_import_index(project_path)
    return len(ops)


def _run_naming_apply(
    project_path: Path,
    report: PipelineReport,
    warnings: list[str],
) -> int:
    splits, _, _ = plan_naming(project_path)
    count = _apply_ops_stage(project_path, splits, report, warnings)
    _, merges, _ = plan_naming(project_path)  # re-plan post-SPLIT
    count += _apply_ops_stage(project_path, merges, report, warnings)
    _, _, renames = plan_naming(project_path)  # re-plan post-MERGE
    count += _apply_ops_stage(project_path, renames, report, warnings, invalidate=False)
    return count


def _run_naming_dryrun(project_path: Path, report: PipelineReport) -> int:
    splits, merges, renames = plan_naming(project_path)
    report.ops.extend(splits)
    report.ops.extend(merges)
    report.ops.extend(renames)
    return len(splits) + len(merges) + len(renames)


def _run_flatten_stage(
    project_path: Path,
    report: PipelineReport,
    warnings: list[str],
    *,
    apply: bool,
) -> int:
    # Drop PATHOLOGICAL ops: they only emit a warning and re-fire every
    # iteration, breaking convergence. Surfaced via collect_unfixable.
    actionable = [
        op
        for op in plan_flatten(project_path)
        if not op.rationale.startswith("PATHOLOGICAL")
    ]
    report.ops.extend(actionable)
    if not (apply and actionable):
        return 0
    warnings.extend(execute(actionable, project_path))
    invalidate_import_index(project_path)
    return len(actionable)


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
    pyramid = "TEST_QUALITY_PYRAMID_LEVEL" in rules
    naming = "TEST_QUALITY_FILE_NAMING" in rules

    # Stage 0.5: relocate non-canonical tier dirs into tests/integration/.
    if apply and pyramid:
        iter_ops += _apply_warning_stage(
            project_path, relocate_non_canonical_tiers, warnings
        )

    # Stage 0: FLATTEN heterogeneous Test* classes (FILE_NAMING preflight).
    if naming:
        iter_ops += _run_flatten_stage(project_path, report, warnings, apply=apply)

    # Stage 1: RELOCATE
    if pyramid:
        iter_ops += (
            _apply_ops_stage(
                project_path, plan_relocate(project_path), report, warnings
            )
            if apply
            else _run_dryrun_ops(plan_relocate(project_path), report)
        )

    # Stage 1.5: FLATTEN_LAYOUT.
    if apply and pyramid:
        iter_ops += _apply_warning_stage(project_path, flatten_tier_layout, warnings)

    # Stages 2-4: FILE_NAMING (planned AFTER flatten + relocate).
    if naming:
        iter_ops += (
            _run_naming_apply(project_path, report, warnings)
            if apply
            else _run_naming_dryrun(project_path, report)
        )
    return iter_ops


def _run_dryrun_ops(ops: list, report: PipelineReport) -> int:
    report.ops.extend(ops)
    return len(ops)


_EXTRACTED_PREFIXES: tuple[str, ...] = (
    "extracted helper `",
    "extracted fixture `",
)


def _run_iterations(
    project_path: Path,
    *,
    apply: bool,
    rules: set[str],
    report: PipelineReport,
    warnings: list[str],
) -> None:
    # B3 fixed-point loop. The cascade of RELOCATE → SPLIT → MERGE →
    # RENAME mutates classification: a test moved across tiers may
    # change its `current_level` (integration tests with no I/O become
    # unit after RELOCATE), a SPLIT may free a NAME_MISMATCH that only
    # appeared because the audit saw the pre-split tuple. Re-iterate
    # until either nothing new is planned or we hit the iteration cap.
    # In dry-run mode we only need one pass (no mutation).
    if not apply:
        _run_one_iteration(
            project_path,
            apply=False,
            rules=rules,
            report=report,
            warnings=warnings,
        )
        report.iterations = 1
        return
    for i in range(MAX_ITERATIONS):
        report.iterations = i + 1
        iter_ops = _run_one_iteration(
            project_path,
            apply=True,
            rules=rules,
            report=report,
            warnings=warnings,
        )
        if iter_ops == 0:
            break


def _parse_extracted_names(extraction_msgs: list[str]) -> set[str]:
    names: set[str] = set()
    for msg in extraction_msgs:
        if "`" not in msg:
            continue
        if not msg.startswith(_EXTRACTED_PREFIXES):
            continue
        names.add(msg.split("`")[1])
    return names


def _is_duplicated_helper_warning(warning: str, extracted_names: set[str]) -> bool:
    if "duplicated in target" not in warning:
        return False
    return any(f"Helper '{n}'" in warning for n in extracted_names)


def _filter_helper_dup_warnings(
    warnings: list[str], extracted_names: set[str]
) -> list[str]:
    if not extracted_names:
        return warnings
    return [
        w for w in warnings if not _is_duplicated_helper_warning(w, extracted_names)
    ]


def _apply_post_polish(project_path: Path, warnings: list[str]) -> list[str]:
    extraction_msgs = _extract_shared_helpers(project_path)
    warnings.extend(extraction_msgs)
    extracted_names = _parse_extracted_names(extraction_msgs)
    warnings = _filter_helper_dup_warnings(warnings, extracted_names)
    warnings.extend(_ruff_format_tests(project_path))
    return warnings


def run(
    project_path: Path,
    *,
    apply: bool = False,
    rules: set[str] | frozenset[str] | None = None,
) -> PipelineReport:
    active_rules: set[str] = set(rules) if rules is not None else set(DEFAULT_RULES)
    report = PipelineReport(applied=apply)
    warnings: list[str] = []

    _run_iterations(
        project_path,
        apply=apply,
        rules=active_rules,
        report=report,
        warnings=warnings,
    )

    if apply:
        warnings = _apply_post_polish(project_path, warnings)

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
                "ruff",
                "check",
                "--fix-only",
                "--select",
                "F401,I001,UP034",
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
            msgs.append(f"{label} returned exit {rc.returncode}: {rc.stderr[:200]}")
    return msgs
