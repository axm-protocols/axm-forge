"""Pure in-memory static checks over a parsed ``batch_edit`` operation set.

Every function here is side-effect free and never touches the filesystem:
file contents are supplied by the caller as ``file -> lines`` mappings.  The
operation schemas are imported from :mod:`axm_edit.models.operations` — this
module declares no parallel schema of its own.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence

from axm_edit.models.check import CheckDiagnostic
from axm_edit.models.operations import CreateOp, DeleteOp, Edit, ReplaceOp, RewriteOp

__all__ = [
    "check_anchor_quotes",
    "check_anchor_whole_line",
    "check_edit_keys",
    "check_rewrite_keys",
    "run_static_checks",
]

REWRITE_UNKNOWN_KEY = "rewrite_unknown_key"
REWRITE_CHECKSUM_REQUIRED = "rewrite_checksum_required"
REWRITE_CHECKSUM_KEY = "checksum"

_REWRITE_DECLARED_KEYS = ("file", "content", REWRITE_CHECKSUM_KEY)
_REWRITE_ALLOWED_KEYS = ("op", *_REWRITE_DECLARED_KEYS)

StaticOperation = ReplaceOp | CreateOp | DeleteOp | RewriteOp
"""Any already-parsed batch operation accepted by the static checks."""

_TRIPLE_QUOTES = ('"""', "'''")


def check_edit_keys(
    op_index: int,
    file: str,
    raw_edit: Mapping[str, object],
) -> list[CheckDiagnostic]:
    """Report keys of ``raw_edit`` that are not part of the ``Edit`` schema.

    Args:
        op_index: 0-indexed position of the operation in the batch.
        file: Relative path targeted by the operation.
        raw_edit: Mapping as authored, before validation.

    Returns:
        A single ``UNKNOWN_EDIT_KEY`` diagnostic, or ``[]`` when every key
        belongs to :class:`~axm_edit.models.operations.Edit`.
    """
    allowed = tuple(Edit.model_fields)
    unknown = sorted(key for key in raw_edit if key not in allowed)
    if not unknown:
        return []
    return [
        CheckDiagnostic(
            op_index=op_index,
            file=file,
            severity="error",
            code="UNKNOWN_EDIT_KEY",
            message=(
                f"unknown edit key(s): {', '.join(unknown)} — "
                f"allowed keys are: {', '.join(allowed)}"
            ),
            hint="An edit accepts only the Edit schema keys; drop the extras.",
        )
    ]


def _declared_checksum(raw_op: Mapping[str, object]) -> str:
    """Return the checksum declared by *raw_op*, or ``""`` when absent."""
    value = raw_op.get(REWRITE_CHECKSUM_KEY)
    return value if isinstance(value, str) else ""


def check_rewrite_keys(
    op_index: int,
    file: str,
    raw_op: Mapping[str, object],
) -> list[CheckDiagnostic]:
    """Report the payload-shape faults of a raw ``rewrite`` operation.

    Pure by construction: the mapping is inspected exactly as authored, no
    path is resolved and no file is read. The on-disk verdict belongs to
    :func:`~axm_edit.core.precheck_fs.check_rewrite_targets`.

    Args:
        op_index: 0-indexed position of the operation in the batch.
        file: Relative path targeted by the operation.
        raw_op: Rewrite mapping as authored, before validation.

    Returns:
        A ``rewrite_unknown_key`` diagnostic naming every out-of-schema key,
        a ``rewrite_checksum_required`` one when no checksum is declared, and
        ``[]`` when the payload holds exactly ``file``, ``content`` and
        ``checksum``.
    """
    diagnostics: list[CheckDiagnostic] = []
    unknown = sorted(key for key in raw_op if key not in _REWRITE_ALLOWED_KEYS)
    if unknown:
        diagnostics.append(
            CheckDiagnostic(
                op_index=op_index,
                file=file,
                severity="error",
                code=REWRITE_UNKNOWN_KEY,
                message=(
                    f"unknown rewrite key(s): {', '.join(unknown)} — "
                    f"allowed keys are: {', '.join(_REWRITE_DECLARED_KEYS)}"
                ),
                hint=(
                    "A `rewrite` accepts only `file`, `content` and "
                    "`checksum`; drop the extras."
                ),
            )
        )
    if not _declared_checksum(raw_op):
        diagnostics.append(
            CheckDiagnostic(
                op_index=op_index,
                file=file,
                severity="error",
                code=REWRITE_CHECKSUM_REQUIRED,
                message=(
                    "a `rewrite` must declare `checksum`, the sha256 hex "
                    "digest of the file bytes it read"
                ),
                hint=(
                    "Read the file, digest its bytes and pass the result as "
                    "`checksum`: a stale digest is a hard refusal and there "
                    "is no overwrite escape hatch."
                ),
            )
        )
    return diagnostics


def check_anchor_quotes(op_index: int, file: str, old: str) -> list[CheckDiagnostic]:
    """Report an anchor containing a triple-quote delimiter.

    Args:
        op_index: 0-indexed position of the operation in the batch.
        file: Relative path targeted by the operation.
        old: The anchor text to inspect.

    Returns:
        A single ``ANCHOR_TRIPLE_QUOTE`` diagnostic, or ``[]``.
    """
    if not any(quote in old for quote in _TRIPLE_QUOTES):
        return []
    return [
        CheckDiagnostic(
            op_index=op_index,
            file=file,
            severity="error",
            code="ANCHOR_TRIPLE_QUOTE",
            message="the anchor contains a triple-quote delimiter",
            hint="Anchor on a quote-free line instead of a docstring body.",
        )
    ]


def _occurrences(text: str, needle: str) -> Iterator[int]:
    """Yield every start offset of ``needle`` in ``text``."""
    start = text.find(needle)
    while start != -1:
        yield start
        start = text.find(needle, start + 1)


def _falls_on_line_boundaries(text: str, start: int, needle: str) -> bool:
    """Whether ``needle`` at ``start`` spans whole lines of ``text``."""
    end = start + len(needle)
    starts_a_line = start == 0 or text[start - 1] == "\n"
    ends_a_line = end == len(text) or text[end] == "\n"
    return starts_a_line and ends_a_line


def check_anchor_whole_line(
    op_index: int,
    file: str,
    lines: Sequence[str],
    old: str,
) -> list[CheckDiagnostic]:
    """Report a multi-line anchor that does not span whole lines.

    Args:
        op_index: 0-indexed position of the operation in the batch.
        file: Relative path targeted by the operation.
        lines: In-memory content of ``file``, one entry per line.
        old: The anchor text to inspect.

    Returns:
        A single ``ANCHOR_NOT_WHOLE_LINE`` diagnostic, or ``[]``.  A
        single-line anchor never yields this code.
    """
    if "\n" not in old:
        return []
    text = "\n".join(lines)
    positions = list(_occurrences(text, old))
    aligned = any(_falls_on_line_boundaries(text, pos, old) for pos in positions)
    if not positions or aligned:
        return []
    return [
        CheckDiagnostic(
            op_index=op_index,
            file=file,
            severity="error",
            code="ANCHOR_NOT_WHOLE_LINE",
            message=(
                "the multi-line anchor starts or ends mid-line in the target file"
            ),
            hint="Extend the anchor to full lines, from column 0 to end of line.",
        )
    ]


def _check_replace(
    op_index: int,
    op: ReplaceOp,
    contents: Mapping[str, Sequence[str]],
) -> list[CheckDiagnostic]:
    """Run every anchor/key check on a single replace operation."""
    lines = contents.get(op.file, ())
    diagnostics: list[CheckDiagnostic] = []
    for edit in op.edits:
        diagnostics.extend(check_edit_keys(op_index, op.file, edit.model_dump()))
        diagnostics.extend(check_anchor_quotes(op_index, op.file, edit.old))
        diagnostics.extend(check_anchor_whole_line(op_index, op.file, lines, edit.old))
    return diagnostics


def run_static_checks(
    operations: Sequence[StaticOperation],
    contents: Mapping[str, Sequence[str]],
) -> list[CheckDiagnostic]:
    """Aggregate every static check over an already-parsed operation set.

    Args:
        operations: Parsed operations, in batch order.
        contents: In-memory ``file -> lines`` mapping; no file is read here.

    Returns:
        Every diagnostic found, sorted by increasing ``op_index``.
    """
    diagnostics = [
        diagnostic
        for index, op in enumerate(operations)
        if isinstance(op, ReplaceOp)
        for diagnostic in _check_replace(index, op, contents)
    ]
    return sorted(diagnostics, key=lambda diagnostic: diagnostic.op_index)
