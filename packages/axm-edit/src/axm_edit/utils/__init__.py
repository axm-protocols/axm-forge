"""Utility functions for axm-edit."""

from __future__ import annotations

from pathlib import Path

__all__ = ["is_binary", "resolve_safe"]

_MAX_BYTES_BINARY_CHECK = 8192
_NONPRINTABLE_THRESHOLD = 0.30
_NONPRINTABLE_UPPER = 0x20
_WHITESPACE = frozenset(b"\t\n\r")


def resolve_safe(root: Path, relative: str) -> Path | None:
    """Resolve *relative* under *root*, returning ``None`` if it escapes.

    This is the **single canonical path resolver** shared by the engine,
    the checkpoint layer and every fs tool. Containment is enforced solely
    by resolving the path (which follows ``..`` segments, symlinks, and
    absolute paths to their real target) and checking the result stays
    under ``root`` — the OS-faithful barrier. No string-level ``..``
    pre-filter is applied, so validation, snapshot and rollback all see
    **exactly the same** set of accepted paths: a path the engine applies
    (e.g. ``sub/../a.py``) is guaranteed to also be captured by the
    checkpoint, closing the rollback hole a divergent filter would open.
    """
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    return resolved


def is_binary(path: Path) -> bool:
    """Return True if the file appears binary.

    Detection: null bytes OR >30% non-printable bytes (excluding
    tab, newline, carriage-return).
    """
    try:
        chunk = path.read_bytes()[:_MAX_BYTES_BINARY_CHECK]
    except OSError:
        return False

    if not chunk:
        return False

    if b"\x00" in chunk:
        return True

    nonprintable = sum(
        1 for b in chunk if b < _NONPRINTABLE_UPPER and b not in _WHITESPACE
    )
    return nonprintable / len(chunk) > _NONPRINTABLE_THRESHOLD
