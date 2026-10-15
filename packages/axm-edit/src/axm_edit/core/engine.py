"""Batch file editing engine.

Implements the validate-then-apply strategy from the axm-edit spec:

1. Read all affected files once (snapshot)
2. Validate **every** operation against the snapshot
3. Resolve line positions (fuzzy search for ``old`` content)
4. Sort replace edits bottom-to-top to avoid line-shift
5. Apply all operations atomically (or fail with 0 files touched)
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from axm_edit.core.anchor_match import (
    anchor_matches_at,
    old_line_count,
    reindent,
    resolve_anchor,
    split_lines,
)
from axm_edit.core.atomic_write import atomic_replace
from axm_edit.core.checkpoint import create_checkpoint, rollback
from axm_edit.core.diagnostics import (
    explain_difference,
    explain_near_miss,
    format_match_lines,
)
from axm_edit.core.rewrite import (
    REWRITE_CHECKSUM_STALE,
    REWRITE_TARGET_MISSING,
    REWRITE_TARGET_NOT_REGULAR,
    classify_rewrite_target,
    compute_checksum,
)
from axm_edit.core.syntax_gate import syntax_regression
from axm_edit.models.operations import (
    BatchResult,
    CreateOp,
    DeleteOp,
    Edit,
    Operation,
    ReplaceOp,
    RewriteOp,
    ValidationError,
)
from axm_edit.utils import is_binary, resolve_safe

logger = logging.getLogger(__name__)

# Canonical resolver, re-exported under the historical internal name so the
# many in-module callers keep working. New code should import
# ``axm_edit.utils.resolve_safe`` directly.
_resolve_safe = resolve_safe


# Preserved verbatim: callers (and tests) match on this exact wording. The
# hint-miss explanation is APPENDED to it, never substituted.
_HINT_MISS_WORDING = "Content not found at or near hint line"

# ── Resolved edit (after fuzzy search) ────────────────────────────────────


@dataclass(frozen=True)
class ResolvedEdit:
    """An edit whose line position has been resolved against the file."""

    line: int  # actual 1-indexed start line found
    old: str
    new: str
    indent: str = ""  # indent prefix to apply to new (from dedent match)


def _detect_eol(path: Path) -> str:
    """Return the dominant end-of-line style of *path* (``\\r\\n`` or ``\\n``).

    The file is read in text mode with universal-newline translation
    disabled so the raw line endings survive. ``\\r\\n`` wins ties; a file
    with no newline (or a pure-LF file) yields ``\\n``.
    """
    with path.open(encoding="utf-8", newline="") as handle:
        text = handle.read()
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    return "\r\n" if crlf > lf else "\n"


def _check_overlaps(
    resolved: list[ResolvedEdit],
) -> list[ValidationError]:
    """Check for overlapping edit ranges within a single file."""
    errors: list[ValidationError] = []

    spans = [(r, r.line, r.line + old_line_count(r.old) - 1) for r in resolved]
    spans.sort(key=lambda t: t[1])

    for i in range(len(spans) - 1):
        _, _, end_a = spans[i]
        edit_b, start_b, _ = spans[i + 1]
        if start_b <= end_a:
            errors.append(
                ValidationError(
                    file="",  # filled by caller
                    line=edit_b.line,
                    error=f"Overlapping edit at line {edit_b.line} "
                    f"(conflicts with edit ending at line {end_a})",
                ),
            )
    return errors


def _hint_miss_message(old: str, actual: str | None, line_count: int) -> str:
    """Explain a hinted miss on top of the preserved not-found wording.

    :data:`_HINT_MISS_WORDING` is kept verbatim and the explanation is
    appended: what actually sits at the hint — delegated to
    :func:`axm_edit.core.diagnostics.explain_difference`, the single owner of
    the character-level comparison — or, when the hint points past the end of
    the file, how many lines the file really has.
    """
    if actual is None:
        return (
            f"{_HINT_MISS_WORDING}: the hint points past the end of the file, "
            f"which has {line_count} lines"
        )
    return f"{_HINT_MISS_WORDING}: {explain_difference(old, actual)}"


def _not_found_error(file_rel: str, edit: Edit, lines: list[str]) -> ValidationError:
    """Build the validation error for an unresolved *edit* (no usable match).

    Branches on the match count of a hint-less edit so a true zero-match
    miss and a ``>=2`` ambiguous anchor produce distinct, actionable
    messages. A hinted edit keeps its dedicated near-hint message, enriched
    by :func:`_hint_miss_message` with what actually sits at the hint line
    (or the file's real line count when the hint points past its end).

    On the zero-match branch the report is delegated to
    :func:`axm_edit.core.diagnostics.explain_near_miss`: it owns every
    marker, Unicode-naming and truncation decision, so the engine only
    transposes its verdict into the structured ``line``/``actual`` fields.

    The ambiguous branch is bounded the same way: the full hit list stays
    available from :func:`~axm_edit.core.anchor_match.resolve_anchor`, but
    its rendering goes through
    :func:`axm_edit.core.diagnostics.format_match_lines`, which lists the
    first few lines and summarises the rest as ``(+N more)``.
    """
    if edit.line is not None:
        actual = _actual_at(lines, edit.line, old_line_count(edit.old))
        return ValidationError(
            file=file_rel,
            line=edit.line,
            expected=edit.old,
            actual=actual,
            error=_hint_miss_message(edit.old, actual, len(lines)),
        )

    match = resolve_anchor(lines, edit.old, None)
    if match.status == "ambiguous":
        hits = list(match.hits)
        line_list = format_match_lines(hits)
        return ValidationError(
            file=file_rel,
            expected=edit.old,
            error=(
                f"Ambiguous match: 'old' snippet found on {len(hits)} lines "
                f"({line_list}); disambiguate with a 'line' hint"
            ),
        )
    near = explain_near_miss([ln.rstrip("\r\n") for ln in lines], edit.old)
    candidate = near.candidate
    return ValidationError(
        file=file_rel,
        line=candidate.line if candidate is not None else None,
        expected=edit.old,
        actual=candidate.text if candidate is not None else None,
        error=near.message,
    )


def _append_not_found_error(
    errors: list[ValidationError],
    file_rel: str,
    edit: Edit,
    lines: list[str],
) -> None:
    """Append a not-found or ambiguous validation error for *edit*."""
    errors.append(_not_found_error(file_rel, edit, lines))


def _resolve_one_edit(lines: list[str], edit: Edit) -> ResolvedEdit | None:
    """Resolve a single edit's position through the shared anchor resolver."""
    match = resolve_anchor(lines, edit.old, edit.line)
    if match.status != "found" or match.line is None:
        return None
    return ResolvedEdit(
        line=match.line,
        old=match.old,
        new=edit.new,
        indent=match.indent,
    )


def _read_editable_lines(
    root: Path,
    file_rel: str,
) -> tuple[list[str] | None, list[ValidationError]]:
    """Resolve, guard and read *file_rel* as a list of text lines.

    Rejects path traversal, missing files, binary files and non-UTF-8 files
    as :class:`ValidationError` verdicts (never raising), so a non-decodable
    file becomes ``BatchResult(success=False)`` rather than an escaping
    ``UnicodeDecodeError``.  On success returns the keepends line list and an
    empty error list.
    """
    target = _resolve_safe(root, file_rel)
    if target is None:
        err = ValidationError(file=file_rel, error="Path traversal not allowed")
        return None, [err]

    if not target.is_file():
        return None, [ValidationError(file=file_rel, error="File not found")]

    if is_binary(target):
        err = ValidationError(file=file_rel, error="Cannot edit a binary file")
        return None, [err]

    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        msg = f"Cannot edit a non-UTF-8 file: {exc}"
        return None, [ValidationError(file=file_rel, error=msg)]

    return split_lines(content), []


def _validate_replace(
    root: Path,
    file_rel: str,
    edits: list[Edit],
) -> tuple[list[ResolvedEdit], list[ValidationError]]:
    """Validate all edits for a file and resolve line positions.

    Returns a tuple of (resolved_edits, errors).  If errors is non-empty,
    resolved_edits should be discarded.
    """
    lines, read_errors = _read_editable_lines(root, file_rel)
    if lines is None:
        return [], read_errors

    errors: list[ValidationError] = []
    resolved: list[ResolvedEdit] = []
    for edit in edits:
        resolved_edit = _resolve_one_edit(lines, edit)
        if resolved_edit is None:
            _append_not_found_error(errors, file_rel, edit, lines)
        else:
            resolved.append(resolved_edit)

    if errors:
        return [], errors

    # Check overlaps after resolution
    overlap_errors = _check_overlaps(resolved)
    for err in overlap_errors:
        err.file = file_rel
    if overlap_errors:
        return [], overlap_errors

    return resolved, []


def _actual_at(lines: list[str], line: int, span: int) -> str | None:
    """Return the actual content at *line* for error reporting."""
    if line < 1 or line > len(lines):
        return None
    end = min(line + span - 1, len(lines))
    return "".join(lines[line - 1 : end]).rstrip("\n")


class _AnchorDriftError(Exception):
    """Raised when the resolved range no longer matches ``old`` at apply time.

    Carries a :class:`ValidationError` describing the drift so the caller
    can surface it on the failed :class:`BatchResult`.
    """

    def __init__(self, detail: ValidationError) -> None:
        super().__init__(detail.error or "Anchor drift detected")
        self.detail = detail


def _anchor_still_matches(lines: list[str], edit: ResolvedEdit) -> bool:
    """Re-confirm ``edit.old`` matches *lines* at the resolved start line.

    Uses the same exact/dedented matchers the resolver relied on, so the
    check stays consistent with how the position was originally found.
    """
    return anchor_matches_at(lines, edit.old, edit.line)


def _replacement_lines(edit: ResolvedEdit) -> list[str]:
    """Return the lines replacing the block matched by *edit*.

    An empty ``new`` is a pure deletion of the matched block: no lines, rather
    than a residual blank line.
    """
    new_content = reindent(edit.new, edit.indent) if edit.indent else edit.new
    if new_content == "":
        return []
    if not new_content.endswith("\n"):
        new_content += "\n"
    return split_lines(new_content)


def _splice(
    lines: list[str],
    resolved: list[ResolvedEdit],
    file_rel: str,
) -> list[str]:
    """Return a copy of *lines* with every resolved edit spliced in.

    Edits are spliced bottom-to-top so upper edits don't shift. Before each
    splice the resolved range is re-verified against ``old`` (TOCTOU guard).

    Raises:
        _AnchorDriftError: When a resolved range no longer matches its anchor.
    """
    spliced = list(lines)
    for edit in sorted(resolved, key=lambda e: e.line, reverse=True):
        if not _anchor_still_matches(spliced, edit):
            raise _AnchorDriftError(
                ValidationError(
                    file=file_rel,
                    line=edit.line,
                    expected=edit.old,
                    error=(
                        "File changed between validation and apply: "
                        f"content at line {edit.line} no longer matches the "
                        "'old' anchor (aborted to avoid a wrong-location splice)"
                    ),
                )
            )
        end = edit.line + old_line_count(edit.old) - 1
        spliced[edit.line - 1 : end] = _replacement_lines(edit)
    return spliced


def _apply_replace(
    root: Path,
    file_rel: str,
    resolved: list[ResolvedEdit],
) -> int:
    """Apply resolved edits to a single file, bottom-to-top.

    Before each splice the resolved range is re-verified against ``old``
    (TOCTOU guard): if the file drifted since validation, the edit is not
    applied and an :class:`_AnchorDriftError` is raised so the caller can
    abort and roll back, rather than splicing at a stale location.

    Returns the number of edits applied.
    """
    target = _resolve_safe(root, file_rel)
    if target is None:  # pragma: no cover - already validated
        raise _AnchorDriftError(
            ValidationError(file=file_rel, error="Path resolution failed at apply"),
        )

    eol = _detect_eol(target)
    lines = split_lines(target.read_text(encoding="utf-8"))
    spliced = _splice(lines, resolved, file_rel)
    target.write_text("".join(spliced), encoding="utf-8", newline=eol)
    return len(resolved)


def _validate_create(root: Path, op: CreateOp) -> list[ValidationError]:
    """Validate a create operation."""
    errors: list[ValidationError] = []
    target = _resolve_safe(root, op.file)
    if target is None:
        errors.append(
            ValidationError(file=op.file, error="Path traversal not allowed"),
        )
        return errors
    if target.exists() and not target.is_file():
        errors.append(
            ValidationError(
                file=op.file,
                error="Target exists and is not a file (is a directory?)",
            ),
        )
    elif target.exists() and not op.overwrite:
        errors.append(
            ValidationError(
                file=op.file,
                error="File already exists (use overwrite: true)",
            ),
        )
    return errors


def _validate_delete(root: Path, op: DeleteOp) -> list[ValidationError]:
    """Validate a delete operation."""
    errors: list[ValidationError] = []
    target = _resolve_safe(root, op.file)
    if target is None:
        errors.append(
            ValidationError(file=op.file, error="Path traversal not allowed"),
        )
        return errors
    if not target.exists():
        errors.append(
            ValidationError(file=op.file, error="File not found"),
        )
    elif not target.is_file():
        errors.append(
            ValidationError(file=op.file, error="Not a file (is a directory?)"),
        )
    return errors


@dataclass(frozen=True)
class _GroupedOps:
    """Operations grouped by type."""

    replace_by_file: dict[str, list[Edit]]
    creates: list[CreateOp]
    deletes: list[DeleteOp]
    rewrites: list[RewriteOp]


def _canonical_key(root: Path, file_rel: str) -> str:
    """Canonical dedup key for *file_rel*: its resolved-within relative path.

    Two spellings of the same file (``"a.py"`` and ``"./a.py"``, or
    ``"sub/../a.py"``) collapse to one key so overlap detection cannot be
    bypassed by aliasing. Paths that escape *root* keep their raw spelling
    and are caught later by per-op validation.
    """
    resolved = resolve_safe(root, file_rel)
    if resolved is None:
        return file_rel
    return resolved.relative_to(root.resolve()).as_posix()


def _group_operations(root: Path, operations: Sequence[Operation]) -> _GroupedOps:
    """Separate operations by type, keying replaces on the canonical path."""
    replace_by_file: dict[str, list[Edit]] = {}
    creates: list[CreateOp] = []
    deletes: list[DeleteOp] = []
    rewrites: list[RewriteOp] = []
    for op in operations:
        if isinstance(op, ReplaceOp):
            key = _canonical_key(root, op.file)
            replace_by_file.setdefault(key, []).extend(op.edits)
        elif isinstance(op, CreateOp):
            creates.append(op)
        elif isinstance(op, DeleteOp):
            deletes.append(op)
        elif isinstance(op, RewriteOp):
            rewrites.append(op)
    return _GroupedOps(replace_by_file, creates, deletes, rewrites)


_REWRITE_TARGET_BINARY = "rewrite_target_binary"

_REWRITE_ERROR_DETAILS: dict[str, str] = {
    REWRITE_TARGET_MISSING: "the rewrite target does not exist",
    REWRITE_TARGET_NOT_REGULAR: "the rewrite target is not a regular file",
    REWRITE_CHECKSUM_STALE: (
        "the rewrite target changed since its declared checksum was read"
    ),
    _REWRITE_TARGET_BINARY: "the rewrite target is a binary file",
}


def _rewrite_error(code: str, file: str) -> ValidationError:
    """Map a rewrite classification *code* to its validation error.

    Pure by construction: the wording derives from the code alone, so the
    diagnostic is testable without touching the filesystem.

    Args:
        code: The code returned by ``classify_rewrite_target`` (or the
            engine-local binary-target code).
        file: The relative path the rewrite targeted.

    Returns:
        A ``ValidationError`` whose message contains *code* verbatim.
    """
    detail = _REWRITE_ERROR_DETAILS.get(code, "the rewrite target was refused")
    return ValidationError(file=file, error=f"{code}: {detail}")


def _observe_rewrite_target(
    root: Path,
    relative: str,
) -> tuple[bool, bool, str | None]:
    """Read the on-disk facts of a rewrite target, without following it.

    The final path component is inspected as-is, so a symlink is observed as
    a symlink and never as the regular file it points at. A path escaping
    *root* is observed as absent, exactly like a path that does not exist.

    Args:
        root: Project root the batch applies to.
        relative: Relative path targeted by the rewrite.

    Returns:
        The ``(exists, is_regular, actual_checksum)`` triple consumed by
        :func:`~axm_edit.core.rewrite.classify_rewrite_target`.
    """
    if _resolve_safe(root, relative) is None:
        return (False, False, None)
    candidate = root / relative
    exists = candidate.exists() or candidate.is_symlink()
    if not exists or candidate.is_symlink() or not candidate.is_file():
        return (exists, False, None)
    try:
        return (True, True, compute_checksum(candidate.read_bytes()))
    except OSError:
        return (True, True, None)


def _validate_rewrite(root: Path, op: RewriteOp) -> list[ValidationError]:
    """Validate one rewrite, before a single byte is written.

    The verdict is not decided here: the observed facts are handed to the
    shared predicate ``classify_rewrite_target``, so the dry run and the
    apply path can never drift apart.
    """
    exists, is_regular, actual = _observe_rewrite_target(root, op.file)
    code = classify_rewrite_target(
        exists=exists,
        is_regular=is_regular,
        actual_checksum=actual,
        expected_checksum=op.expected_checksum,
    )
    if code is not None:
        return [_rewrite_error(code, op.file)]
    target = _resolve_safe(root, op.file)
    if target is not None and is_binary(target):
        return [_rewrite_error(_REWRITE_TARGET_BINARY, op.file)]
    return []


def _validate_all(
    root: Path,
    grouped: _GroupedOps,
) -> tuple[dict[str, list[ResolvedEdit]], list[ValidationError]]:
    """Validate all operations and resolve replace positions."""
    errors: list[ValidationError] = []
    resolved_by_file: dict[str, list[ResolvedEdit]] = {}

    for file_rel, edits in grouped.replace_by_file.items():
        resolved, file_errors = _validate_replace(root, file_rel, edits)
        if file_errors:
            errors.extend(file_errors)
        else:
            resolved_by_file[file_rel] = resolved

    for create_op in grouped.creates:
        errors.extend(_validate_create(root, create_op))

    for delete_op in grouped.deletes:
        errors.extend(_validate_delete(root, delete_op))

    for rewrite_op in grouped.rewrites:
        errors.extend(_validate_rewrite(root, rewrite_op))

    return resolved_by_file, errors


def _apply_creates_deletes(
    root: Path,
    creates: list[CreateOp],
    deletes: list[DeleteOp],
) -> int:
    """Apply create and delete operations, returning count applied."""
    count = 0
    for create_op in creates:
        target = _resolve_safe(root, create_op.file)
        assert target is not None
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(create_op.content, encoding="utf-8", newline="")
        count += 1
    for delete_op in deletes:
        target = _resolve_safe(root, delete_op.file)
        assert target is not None
        target.unlink()
        count += 1
    return count


def _apply_rewrites(root: Path, rewrites: list[RewriteOp]) -> int:
    """Replace every validated rewrite target atomically, returning the count."""
    count = 0
    for rewrite_op in rewrites:
        target = _resolve_safe(root, rewrite_op.file)
        assert target is not None
        atomic_replace(target, rewrite_op.content.encode("utf-8"))
        count += 1
    return count


def _current_text(root: Path, file_rel: str) -> str | None:
    """Read *file_rel* as UTF-8 text, ``None`` when absent or unreadable."""
    target = _resolve_safe(root, file_rel)
    if target is None or not target.is_file():
        return None
    try:
        return target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _planned_contents(
    root: Path,
    grouped: _GroupedOps,
    resolved_by_file: dict[str, list[ResolvedEdit]],
) -> Iterator[tuple[str, str | None, str]]:
    """Yield ``(file, before, after)`` for every file the batch would write.

    A replace target that drifted since its resolution is skipped: the apply
    step re-detects the drift and rolls the batch back.
    """
    for file_rel, resolved in resolved_by_file.items():
        before = _current_text(root, file_rel)
        if before is None:
            continue
        try:
            spliced = _splice(split_lines(before), resolved, file_rel)
        except _AnchorDriftError:
            continue
        yield file_rel, before, "".join(spliced)
    for create_op in grouped.creates:
        yield create_op.file, _current_text(root, create_op.file), create_op.content
    for rewrite_op in grouped.rewrites:
        yield rewrite_op.file, _current_text(root, rewrite_op.file), rewrite_op.content


def _syntax_errors(
    root: Path,
    grouped: _GroupedOps,
    resolved_by_file: dict[str, list[ResolvedEdit]],
) -> list[ValidationError]:
    """Refuse Python, TOML or JSON syntax regressions before writing."""
    errors: list[ValidationError] = []
    for file_rel, before, after in _planned_contents(root, grouped, resolved_by_file):
        error = syntax_regression(file_rel, before, after)
        if error is not None:
            errors.append(error)
    return errors


def batch_apply(root: Path, operations: Sequence[Operation]) -> BatchResult:
    """Validate and apply a batch of file operations.

    Atomicity contract:

    * **Validation is the gate.** All operations are validated first; if any
      fails the batch is rejected wholesale (``success=False``) before a
      single byte is written — a true all-or-nothing guarantee. Validation
      includes the syntax gate: a batch that would leave a parseable Python, TOML
      or JSON file unparseable is refused (:mod:`axm_edit.core.syntax_gate`).
      JSON comments and trailing commas are tolerated; new JSON files are
      unchecked.
    * **Apply is best-effort with automatic rollback.** Once validation
      passes, a targeted checkpoint of every touched path is captured and the
      operations are applied. If *any* exception occurs mid-apply (anchor
      drift, a ``write_text`` / ``unlink`` / ``mkdir`` failure, a permission
      error, …) the partial work is rolled back to that checkpoint — touched
      files are restored to their pre-batch bytes and batch-created files (and
      the empty directories created for them) are removed — and a failing
      ``BatchResult`` is returned. The filesystem is *not* made transactional
      at the OS level; the rollback restores only the snapshotted paths.

    Args:
        root: Project root directory (all paths are relative to this).
        operations: List of replace, create, rewrite and delete operations.

    Returns:
        BatchResult with success status, a targeted-path snapshot
        (``checkpoint``) for rollback, and a summary.
    """
    root = root.resolve()
    grouped = _group_operations(root, operations)
    resolved_by_file, errors = _validate_all(root, grouped)
    if not errors:
        errors = _syntax_errors(root, grouped, resolved_by_file)

    if errors:
        return BatchResult(
            success=False,
            error="Validation failed",
            details=errors,
        )

    checkpoint = create_checkpoint(root, operations)

    try:
        total_applied = 0
        for file_rel, resolved in resolved_by_file.items():
            total_applied += _apply_replace(root, file_rel, resolved)
        total_applied += _apply_creates_deletes(root, grouped.creates, grouped.deletes)
        total_applied += _apply_rewrites(root, grouped.rewrites)
    except _AnchorDriftError as drift:
        rb = rollback(root, checkpoint)
        return BatchResult(
            success=False,
            checkpoint=checkpoint,
            error="Apply aborted: file drifted between validation and apply",
            details=[drift.detail],
            rollback_failed=not rb.ok,
        )
    except Exception as exc:  # noqa: BLE001 - any apply failure must roll back
        rb = rollback(root, checkpoint)
        return BatchResult(
            success=False,
            checkpoint=checkpoint,
            error=f"Apply aborted and rolled back: {exc}",
            rollback_failed=not rb.ok,
        )

    summary = {
        "modified": len(resolved_by_file),
        "created": len(grouped.creates),
        "deleted": len(grouped.deletes),
    }
    if grouped.rewrites:
        summary["rewritten"] = len(grouped.rewrites)

    return BatchResult(
        success=True,
        checkpoint=checkpoint,
        applied=total_applied,
        summary=summary,
    )
