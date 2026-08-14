"""Single read-only preflight core shared by both ``batch_edit`` surfaces.

The rules themselves live in :mod:`axm_edit.core.precheck` (pure, in-memory)
and :mod:`axm_edit.core.precheck_fs` (filesystem-resolving). This module owns
no rule: it *orchestrates* them over a raw batch payload, merges their
diagnostics into one deterministically ordered list, and partitions that list
into a blocking / non-blocking report both tool surfaces can consume.

Strictly read-only: every path resolution is delegated to the checks (which
go through ``resolve_safe``), and nothing here opens a file for writing,
creates a temporary file or takes a checkpoint.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from axm_edit.core.precheck import check_edit_keys, check_rewrite_keys
from axm_edit.core.precheck_fs import run_fs_checks
from axm_edit.models.check import CheckDiagnostic, PreflightReport
from axm_edit.models.operations import Edit

__all__ = [
    "collect_preflight_diagnostics",
    "merge_diagnostics",
    "partition_diagnostics",
]

_BLOCKING_BY_SEVERITY: dict[str, bool] = {"error": True, "warning": False}
"""Severity token -> whether it blocks. Extend here, never in the callers."""

_UNKNOWN_SEVERITY_BLOCKS = True
"""Fail-closed verdict for a severity token absent from the mapping."""

_UNKNOWN_FILE = "<unknown>"

_REWRITE_OP = "rewrite"


def _sort_key(diagnostic: CheckDiagnostic) -> tuple[int, str, str]:
    """Order by operation index, then rule family (``code``), then message."""
    return (diagnostic.op_index, diagnostic.code, diagnostic.message)


def merge_diagnostics(
    *groups: Sequence[CheckDiagnostic],
) -> list[CheckDiagnostic]:
    """Merge diagnostic groups into one deterministically ordered list.

    Args:
        groups: One diagnostic sequence per rule layer, in any order.

    Returns:
        Every diagnostic, ordered by ``(op_index, rule family, message)``;
        the same input always yields an equal list.
    """
    return sorted(
        (diagnostic for group in groups for diagnostic in group),
        key=_sort_key,
    )


def _edit_mappings(raw_op: Mapping[str, object]) -> list[Mapping[str, object]]:
    """Return the raw ``edits`` mappings of *raw_op*, as authored."""
    raw_edits = raw_op.get("edits")
    if not isinstance(raw_edits, list):
        return []
    return [
        cast("Mapping[str, object]", item)
        for item in cast("list[object]", raw_edits)
        if isinstance(item, Mapping)
    ]


def _op_file(raw_op: Mapping[str, object]) -> str:
    """Return the relative path of *raw_op*, or a placeholder when absent."""
    file = raw_op.get("file")
    return file if isinstance(file, str) and file else _UNKNOWN_FILE


def _sanitised_op(raw_op: Mapping[str, object]) -> Mapping[str, object]:
    """Drop unknown edit keys so the schema-strict parsing stage survives.

    The unknown keys are already reported by :func:`check_edit_keys`; keeping
    them would make the ``Operation`` adapter reject the whole batch and hide
    every other diagnostic.
    """
    edits = _edit_mappings(raw_op)
    if not edits:
        return raw_op
    allowed = frozenset(Edit.model_fields)
    cleaned = [
        {key: value for key, value in edit.items() if key in allowed} for edit in edits
    ]
    return {**raw_op, "edits": cleaned}


def _check_unknown_edit_keys(
    raw_ops: Sequence[Mapping[str, object]],
) -> list[CheckDiagnostic]:
    """Run the unknown-edit-key rule on the raw, pre-validation payload."""
    return [
        diagnostic
        for index, raw_op in enumerate(raw_ops)
        for raw_edit in _edit_mappings(raw_op)
        for diagnostic in check_edit_keys(index, _op_file(raw_op), raw_edit)
    ]


def _check_rewrite_keys(
    raw_ops: Sequence[Mapping[str, object]],
) -> list[CheckDiagnostic]:
    """Run the rewrite payload-shape rule on the raw, pre-validation batch."""
    return [
        diagnostic
        for index, raw_op in enumerate(raw_ops)
        if raw_op.get("op") == _REWRITE_OP
        for diagnostic in check_rewrite_keys(index, _op_file(raw_op), raw_op)
    ]


def collect_preflight_diagnostics(
    root: Path,
    raw_ops: Sequence[Mapping[str, object]],
) -> list[CheckDiagnostic]:
    """Collect every preflight diagnostic for a raw batch, without writing.

    Merges the key rules that need the payload *as authored* (unknown edit
    keys, rewrite payload shape) with the static and filesystem rules of
    :func:`~axm_edit.core.precheck_fs.run_fs_checks`.

    Args:
        root: Project root the batch would be applied to.
        raw_ops: Operations in batch order, as authored (raw mappings).

    Returns:
        Every diagnostic, ordered by ``(op_index, rule family, message)``.
    """
    unknown_keys = _check_unknown_edit_keys(raw_ops)
    rewrite_keys = _check_rewrite_keys(raw_ops)
    sanitised = [_sanitised_op(raw_op) for raw_op in raw_ops]
    return merge_diagnostics(
        unknown_keys,
        rewrite_keys,
        run_fs_checks(root, sanitised),
    )


def _is_blocking(severity: str) -> bool:
    """Resolve a severity token through the extensible blocking mapping."""
    return _BLOCKING_BY_SEVERITY.get(severity, _UNKNOWN_SEVERITY_BLOCKS)


def partition_diagnostics(
    diagnostics: Sequence[CheckDiagnostic],
) -> PreflightReport:
    """Split *diagnostics* into blocking errors and informative warnings.

    Args:
        diagnostics: Diagnostics in the order they should be reported.

    Returns:
        A :class:`~axm_edit.models.check.PreflightReport` whose ``errors``
        and ``warnings`` preserve the input order and whose ``blocking`` is
        True iff at least one diagnostic blocks the batch.
    """
    ordered = list(diagnostics)
    errors = [item for item in ordered if _is_blocking(item.severity)]
    warnings = [item for item in ordered if not _is_blocking(item.severity)]
    return PreflightReport(
        diagnostics=ordered,
        errors=errors,
        warnings=warnings,
        blocking=bool(errors),
    )
