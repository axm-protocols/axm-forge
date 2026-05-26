"""Utility functions for axm-edit."""

from __future__ import annotations

from pathlib import Path

__all__ = ["is_binary"]

_MAX_BYTES_BINARY_CHECK = 8192
_NONPRINTABLE_THRESHOLD = 0.30
_NONPRINTABLE_UPPER = 0x20
_WHITESPACE = frozenset(b"\t\n\r")


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
