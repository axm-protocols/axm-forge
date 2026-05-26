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
import textwrap
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

from axm_edit.core.checkpoint import create_checkpoint
from axm_edit.models.operations import (
    BatchResult,
    CreateOp,
    DeleteOp,
    Edit,
    Operation,
    ReplaceOp,
    ValidationError,
)

logger = logging.getLogger(__name__)

# ── Resolved edit (after fuzzy search) ────────────────────────────────────


@dataclass(frozen=True)
class ResolvedEdit:
    """An edit whose line position has been resolved against the file."""

    line: int  # actual 1-indexed start line found
    old: str
    new: str
    indent: str = ""  # indent prefix to apply to new (from dedent match)


# ── Helpers ───────────────────────────────────────────────────────────────


def _resolve_safe(root: Path, relative: str) -> Path | None:
    """Resolve a relative path safely within *root*.

    Returns ``None`` if the path escapes the project root.
    """
    if ".." in relative.split("/"):
        return None
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    return resolved


def _old_line_count(old: str) -> int:
    """Return the number of file lines spanned by *old*."""
    return old.rstrip("\n").count("\n") + 1


def _dedent_block(text: str) -> str:
    """Fully dedent a block of text for comparison."""
    return textwrap.dedent(text).strip("\n")


def _detect_indent(lines: list[str], start: int, num_lines: int) -> str:
    """Detect the common leading whitespace of a block in the file."""
    block_lines = lines[start - 1 : start - 1 + num_lines]
    non_empty = [ln for ln in block_lines if ln.strip()]
    if not non_empty:
        return ""
    # Find shortest leading whitespace among non-empty lines
    min_indent = min(len(ln) - len(ln.lstrip()) for ln in non_empty)
    return non_empty[0][:min_indent]


def _reindent(text: str, indent: str) -> str:
    """Dedent *text* fully, then prepend *indent* to each non-empty line.

    Preserves relative indentation within the block.
    """
    dedented = textwrap.dedent(text)
    result_lines = []
    for line in dedented.splitlines(keepends=True):
        if line.strip():  # non-empty line
            result_lines.append(indent + line)
        else:
            result_lines.append(line)  # keep blank lines as-is
    return "".join(result_lines)


# ── Normalization helpers ─────────────────────────────────────────────────

_SMART_QUOTE_MAP: dict[str, str] = {
    "\u201c": '"',  # left double
    "\u201d": '"',  # right double
    "\u2018": "'",  # left single
    "\u2019": "'",  # right single
}


def _normalize_quotes(text: str) -> str:
    """Replace smart (curly) quotes with their ASCII equivalents."""
    for smart, straight in _SMART_QUOTE_MAP.items():
        text = text.replace(smart, straight)
    return text


def _try_normalize_old(old: str) -> list[str]:
    """Return normalized variants of *old* to retry matching.

    Variants tried (in order):
    1. Smart-quote normalization (curly → straight).
    2. Strip wrapping double-quotes (LLM artifact).

    Returns only variants that differ from the original.
    """
    variants: list[str] = []

    # Variant 1: smart quotes → straight
    normalized = _normalize_quotes(old)
    if normalized != old:
        variants.append(normalized)

    # Variant 2: strip wrapping quotes
    if old.startswith('"') and old.endswith('"') and len(old) > len('""'):
        stripped = old[1:-1]
        if stripped and stripped != old:
            variants.append(stripped)

    return variants


# ── Match helpers ─────────────────────────────────────────────────────────

_MatchFn: TypeAlias = Callable[[int], bool]  # noqa: UP040 — radon crashes on `type` stmt
_MatchResult: TypeAlias = "tuple[int, str] | None"  # noqa: UP040


def _make_matchers(
    lines: list[str],
    old: str,
) -> tuple[_MatchFn, _MatchFn, int]:
    """Build exact and dedented match functions for *old* against *lines*.

    Returns ``(match_exact, match_dedented, num_lines)``.
    """
    old_stripped = old.rstrip("\n")
    old_dedented = _dedent_block(old)
    num_lines = _old_line_count(old)

    def match_exact(start: int) -> bool:
        """Check if *old* matches at 1-indexed *start* (exact)."""
        if start < 1 or start + num_lines - 1 > len(lines):
            return False
        block = "".join(lines[start - 1 : start - 1 + num_lines])
        return block.rstrip("\n") == old_stripped

    def match_dedented(start: int) -> bool:
        """Check if *old* matches at *start* after dedenting both."""
        if start < 1 or start + num_lines - 1 > len(lines):
            return False
        block = "".join(lines[start - 1 : start - 1 + num_lines])
        return _dedent_block(block) == old_dedented

    return match_exact, match_dedented, num_lines


def _search_near_hint(
    lines: list[str],
    hint_line: int,
    match_fn: _MatchFn,
    num_lines: int,
    *,
    dedented: bool = False,
) -> _MatchResult:
    """Search at *hint_line* then expand ±5 lines.

    Returns ``(line, indent)`` on match, ``None`` otherwise.
    """

    def _get_indent(start: int) -> str:
        return _detect_indent(lines, start, num_lines) if dedented else ""

    if match_fn(hint_line):
        return (hint_line, _get_indent(hint_line))
    for delta in range(1, 6):
        for candidate in (hint_line - delta, hint_line + delta):
            if match_fn(candidate):
                return (candidate, _get_indent(candidate))
    return None


def _scan_all_lines(
    lines: list[str],
    match_fn: _MatchFn,
    num_lines: int,
    *,
    dedented: bool = False,
) -> _MatchResult:
    """Full-file scan for a single unambiguous match.

    Returns ``(line, indent)`` if exactly one match, ``None`` otherwise.
    """
    hits: list[int] = []
    for start in range(1, len(lines) - num_lines + 2):
        if match_fn(start):
            hits.append(start)
    if len(hits) == 1:
        indent = _detect_indent(lines, hits[0], num_lines) if dedented else ""
        return (hits[0], indent)
    return None


# ── Main search orchestrator ──────────────────────────────────────────────


def _find_old(
    lines: list[str],
    old: str,
    hint_line: int | None,
) -> _MatchResult:
    """Find *old* content in *lines*, returning (1-indexed line, indent_prefix).

    Strategy:
        1. If *hint_line* given → check at that exact position first.
        2. Expand outward ±5 lines from the hint.
        3. Fall back to full-file scan.
        4. If *hint_line* is ``None`` → full-file scan immediately.

    Matching modes (tried in order):
        - **Exact**: ``old`` matches the file block byte-for-byte.
          Returns ``indent=""`` (no re-indent needed).
        - **Indent-normalized**: both ``old`` and the file block are
          fully dedented before comparison.
          Returns the file block's indent prefix so ``new`` can be
          re-indented to match.

    Returns ``None`` if zero or multiple matches are found (ambiguous).
    """
    match_exact, match_dedented, num_lines = _make_matchers(lines, old)

    # ── Pass 1: exact match
    if hint_line is not None:
        result = _search_near_hint(lines, hint_line, match_exact, num_lines)
        if result:
            return result
    result = _scan_all_lines(lines, match_exact, num_lines)
    if result:
        return result

    # ── Pass 2: indent-normalized match
    if hint_line is not None:
        result = _search_near_hint(
            lines,
            hint_line,
            match_dedented,
            num_lines,
            dedented=True,
        )
        if result:
            return result
    return _scan_all_lines(lines, match_dedented, num_lines, dedented=True)


def _check_overlaps(
    resolved: list[ResolvedEdit],
) -> list[ValidationError]:
    """Check for overlapping edit ranges within a single file."""
    errors: list[ValidationError] = []

    spans = [(r, r.line, r.line + _old_line_count(r.old) - 1) for r in resolved]
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


def _append_not_found_error(
    errors: list[ValidationError],
    file_rel: str,
    edit: Edit,
    lines: list[str],
) -> None:
    """Append a 'not found' validation error for *edit*."""
    if edit.line is not None:
        errors.append(
            ValidationError(
                file=file_rel,
                line=edit.line,
                expected=edit.old,
                actual=_actual_at(
                    lines,
                    edit.line,
                    _old_line_count(edit.old),
                ),
                error="Content not found at or near hint line",
            ),
        )
    else:
        errors.append(
            ValidationError(
                file=file_rel,
                expected=edit.old,
                error="Content not found in file (0 or ambiguous matches)",
            ),
        )


def _validate_replace(  # noqa: C901
    root: Path,
    file_rel: str,
    edits: list[Edit],
) -> tuple[list[ResolvedEdit], list[ValidationError]]:
    """Validate all edits for a file and resolve line positions.

    Returns a tuple of (resolved_edits, errors).  If errors is non-empty,
    resolved_edits should be discarded.
    """
    errors: list[ValidationError] = []
    resolved: list[ResolvedEdit] = []

    target = _resolve_safe(root, file_rel)
    if target is None:
        errors.append(
            ValidationError(file=file_rel, error="Path traversal not allowed"),
        )
        return [], errors

    if not target.is_file():
        errors.append(
            ValidationError(file=file_rel, error="File not found"),
        )
        return [], errors

    lines = target.read_text().splitlines(keepends=True)

    # Resolve each edit's position via fuzzy search
    for edit in edits:
        result = _find_old(lines, edit.old, edit.line)

        # ── Normalization fallback ────────────────────────────────
        effective_old = edit.old
        if result is None:
            for variant in _try_normalize_old(edit.old):
                result = _find_old(lines, variant, edit.line)
                if result is not None:
                    effective_old = variant
                    break

        if result is None:
            _append_not_found_error(errors, file_rel, edit, lines)
        else:
            found_line, indent = result
            resolved.append(
                ResolvedEdit(
                    line=found_line,
                    old=effective_old,
                    new=edit.new,
                    indent=indent,
                ),
            )

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


def _apply_replace(
    root: Path,
    file_rel: str,
    resolved: list[ResolvedEdit],
) -> int:
    """Apply resolved edits to a single file, bottom-to-top.

    Returns the number of edits applied.
    """
    target = _resolve_safe(root, file_rel)
    assert target is not None  # already validated

    lines = target.read_text().splitlines(keepends=True)

    # Sort bottom-to-top so upper edits don't shift
    sorted_edits = sorted(resolved, key=lambda e: e.line, reverse=True)

    for edit in sorted_edits:
        start = edit.line
        end = start + _old_line_count(edit.old) - 1
        # Build replacement lines, preserving trailing newline style
        new_content = edit.new
        # Re-indent if match was indent-normalized
        if edit.indent:
            new_content = _reindent(new_content, edit.indent)
        if not new_content.endswith("\n"):
            new_content += "\n"
        new_lines = new_content.splitlines(keepends=True)
        lines[start - 1 : end] = new_lines

    target.write_text("".join(lines))
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
    if target.exists() and not op.overwrite:
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
    return errors


@dataclass(frozen=True)
class _GroupedOps:
    """Operations grouped by type."""

    replace_by_file: dict[str, list[Edit]]
    creates: list[CreateOp]
    deletes: list[DeleteOp]


def _group_operations(operations: Sequence[Operation]) -> _GroupedOps:
    """Separate operations by type."""
    replace_by_file: dict[str, list[Edit]] = {}
    creates: list[CreateOp] = []
    deletes: list[DeleteOp] = []
    for op in operations:
        if isinstance(op, ReplaceOp):
            replace_by_file.setdefault(op.file, []).extend(op.edits)
        elif isinstance(op, CreateOp):
            creates.append(op)
        elif isinstance(op, DeleteOp):
            deletes.append(op)
    return _GroupedOps(replace_by_file, creates, deletes)


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
        target.write_text(create_op.content)
        count += 1
    for delete_op in deletes:
        target = _resolve_safe(root, delete_op.file)
        assert target is not None
        target.unlink()
        count += 1
    return count


def batch_apply(root: Path, operations: Sequence[Operation]) -> BatchResult:
    """Validate and apply a batch of file operations atomically.

    Args:
        root: Project root directory (all paths are relative to this).
        operations: List of replace, create, and delete operations.

    Returns:
        BatchResult with success status, checkpoint SHA, and summary.
    """
    root = root.resolve()
    grouped = _group_operations(operations)
    resolved_by_file, errors = _validate_all(root, grouped)

    if errors:
        return BatchResult(
            success=False,
            error="Validation failed",
            details=errors,
        )

    checkpoint = create_checkpoint(root)

    total_applied = 0
    for file_rel, resolved in resolved_by_file.items():
        total_applied += _apply_replace(root, file_rel, resolved)
    total_applied += _apply_creates_deletes(root, grouped.creates, grouped.deletes)

    return BatchResult(
        success=True,
        checkpoint=checkpoint,
        applied=total_applied,
        summary={
            "modified": len(resolved_by_file),
            "created": len(grouped.creates),
            "deleted": len(grouped.deletes),
        },
    )
