"""Filesystem-resolving prechecks over a ``batch_edit`` operation set.

This layer sits on top of the pure in-memory checks of
:mod:`axm_edit.core.precheck` and adds the only diagnostics that require
looking at the disk: a ``create`` aimed at an existing path, an anchor that
is absent from (or duplicated in) the real file, and a line that is wider
than the 88-char default ``batch_edit`` lints against yet still legal for
the project.

Strictly read-only: every path goes through :func:`resolve_safe`, and files
are only probed (``is_file``) and read (``read_text``). Nothing here creates,
mutates or removes anything on disk.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from pydantic import TypeAdapter

from axm_edit.core.precheck import StaticOperation, run_static_checks
from axm_edit.models.check import CheckDiagnostic
from axm_edit.models.operations import CreateOp, DeleteOp, Operation, ReplaceOp
from axm_edit.services.line_length import DEFAULT_LINE_LENGTH, resolve_line_length
from axm_edit.utils import is_binary, resolve_safe

__all__ = [
    "check_anchors_on_disk",
    "check_create_targets",
    "check_line_length",
    "run_fs_checks",
]

type FsOperation = StaticOperation | Mapping[str, object]

_OPERATION_ADAPTER: TypeAdapter[StaticOperation] = TypeAdapter(Operation)

_CREATE_ON_EXISTING_HINT = (
    "Target a free path, use a `replace`, or set `overwrite: true`: a "
    "`delete` followed by a `create` is NOT an atomic replacement — the "
    "batch can fail in between and leave the file gone."
)
_ANCHOR_NOT_FOUND_HINT = (
    "Re-read the file and copy the anchor verbatim, whitespace included."
)
_ANCHOR_AMBIGUOUS_HINT = (
    "Extend the anchor with surrounding context (or pin `line`): "
    "`batch_edit` rewrites the first match only."
)
_LINE_LENGTH_HINT = (
    "`batch_edit` lints with ruff's 88-char default, so this line may be "
    "reflowed even though the project allows it."
)


def _parse(operations: Sequence[FsOperation]) -> list[StaticOperation]:
    """Normalise raw payload mappings into parsed operation models."""
    return [
        op
        if isinstance(op, CreateOp | ReplaceOp | DeleteOp)
        else _OPERATION_ADAPTER.validate_python(op)
        for op in operations
    ]


def _exists(root: Path, relative: str) -> bool:
    """Return True when *relative* resolves under *root* and exists."""
    resolved = resolve_safe(root, relative)
    return resolved is not None and resolved.exists()


def _read_text(root: Path, relative: str) -> str | None:
    """Read *relative* under *root*, or ``None`` when it is unreadable."""
    resolved = resolve_safe(root, relative)
    if resolved is None or not resolved.is_file() or is_binary(resolved):
        return None
    try:
        return resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def check_create_targets(
    root: Path,
    operations: Sequence[FsOperation],
) -> list[CheckDiagnostic]:
    """Flag every ``create`` whose target already exists under *root*.

    Args:
        root: Project root the batch would be applied to.
        operations: Operations in batch order (models or raw payloads).

    Returns:
        One ``CREATE_ON_EXISTING`` error per colliding create, else ``[]``.
    """
    return [
        CheckDiagnostic(
            op_index=index,
            file=op.file,
            severity="error",
            code="CREATE_ON_EXISTING",
            message=f"`create` targets {op.file!r}, which already exists.",
            hint=_CREATE_ON_EXISTING_HINT,
        )
        for index, op in enumerate(_parse(operations))
        if isinstance(op, CreateOp) and _exists(root, op.file)
    ]


def _check_anchors(
    op_index: int,
    op: ReplaceOp,
    text: str,
) -> list[CheckDiagnostic]:
    """Compare every anchor of *op* against the file *text* read on disk."""
    diagnostics: list[CheckDiagnostic] = []
    for edit in op.edits:
        occurrences = text.count(edit.old)
        if occurrences == 0:
            diagnostics.append(
                CheckDiagnostic(
                    op_index=op_index,
                    file=op.file,
                    severity="error",
                    code="ANCHOR_NOT_FOUND",
                    message=f"Anchor not found in {op.file!r}: {edit.old!r}.",
                    hint=_ANCHOR_NOT_FOUND_HINT,
                )
            )
        elif occurrences > 1:
            diagnostics.append(
                CheckDiagnostic(
                    op_index=op_index,
                    file=op.file,
                    severity="warning",
                    code="ANCHOR_AMBIGUOUS",
                    message=(
                        f"Anchor found {occurrences} times in {op.file!r}: "
                        f"{edit.old!r}."
                    ),
                    hint=_ANCHOR_AMBIGUOUS_HINT,
                )
            )
    return diagnostics


def check_anchors_on_disk(
    root: Path,
    operations: Sequence[FsOperation],
) -> list[CheckDiagnostic]:
    """Resolve every ``replace`` anchor against the file actually on disk.

    Args:
        root: Project root the batch would be applied to.
        operations: Operations in batch order (models or raw payloads).

    Returns:
        ``ANCHOR_NOT_FOUND`` errors for missing anchors and
        ``ANCHOR_AMBIGUOUS`` warnings for anchors matching more than once;
        ``[]`` when every anchor matches exactly once.
    """
    diagnostics: list[CheckDiagnostic] = []
    for index, op in enumerate(_parse(operations)):
        if not isinstance(op, ReplaceOp):
            continue
        text = _read_text(root, op.file)
        if text is None:
            continue
        diagnostics.extend(_check_anchors(index, op, text))
    return diagnostics


def check_line_length(
    op_index: int,
    file: str,
    new: str,
    limit: int,
) -> list[CheckDiagnostic]:
    """Flag lines of *new* wider than 88 chars but within *limit*.

    Pure function: no path is resolved and no file is read.

    Args:
        op_index: 0-indexed position of the operation in the batch.
        file: Relative path targeted by that operation.
        new: Replacement (or created) text to measure, line by line.
        limit: The project's configured ``line-length``.

    Returns:
        One ``LINE_LENGTH_DEFAULT_MISMATCH`` warning per line in the
        ``]88, limit]`` window, else ``[]``.
    """
    return [
        CheckDiagnostic(
            op_index=op_index,
            file=file,
            severity="warning",
            code="LINE_LENGTH_DEFAULT_MISMATCH",
            message=(
                f"Line {number} is {len(line)} chars: over the "
                f"{DEFAULT_LINE_LENGTH}-char default but within the "
                f"configured limit of {limit}."
            ),
            hint=_LINE_LENGTH_HINT,
        )
        for number, line in enumerate(new.splitlines(), start=1)
        if DEFAULT_LINE_LENGTH < len(line) <= limit
    ]


def _check_line_lengths(
    operations: Sequence[StaticOperation],
    limit: int,
) -> list[CheckDiagnostic]:
    """Apply :func:`check_line_length` to every text the batch would write."""
    diagnostics: list[CheckDiagnostic] = []
    for index, op in enumerate(operations):
        if isinstance(op, CreateOp):
            diagnostics.extend(check_line_length(index, op.file, op.content, limit))
        elif isinstance(op, ReplaceOp):
            for edit in op.edits:
                diagnostics.extend(check_line_length(index, op.file, edit.new, limit))
    return diagnostics


def _read_contents(
    root: Path,
    operations: Iterable[StaticOperation],
) -> dict[str, list[str]]:
    """Read every targeted file once into the ``file -> lines`` mapping."""
    contents: dict[str, list[str]] = {}
    for op in operations:
        if op.file in contents:
            continue
        text = _read_text(root, op.file)
        if text is not None:
            contents[op.file] = text.splitlines()
    return contents


def run_fs_checks(
    root: Path,
    operations: Sequence[FsOperation],
) -> list[CheckDiagnostic]:
    """Aggregate every filesystem-resolving check plus the static ones.

    The static checks of :func:`run_static_checks` are delegated with the
    contents read from disk, so they see the real files instead of an
    empty mapping. The whole pass is read-only.

    Args:
        root: Project root the batch would be applied to.
        operations: Operations in batch order (models or raw payloads).

    Returns:
        Every diagnostic found, sorted by increasing ``op_index``.
    """
    parsed = _parse(operations)
    limit = resolve_line_length(root)
    contents = _read_contents(root, parsed)
    diagnostics = [
        *check_create_targets(root, parsed),
        *check_anchors_on_disk(root, parsed),
        *_check_line_lengths(parsed, limit),
        *run_static_checks(parsed, contents),
    ]
    return sorted(diagnostics, key=lambda diagnostic: diagnostic.op_index)
