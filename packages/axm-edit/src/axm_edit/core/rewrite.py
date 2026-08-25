"""Pure classification of a whole-file rewrite target.

The predicate below is the SINGLE source of truth shared by
``batch_edit_check`` (dry-run diagnostics) and ``batch_edit`` (apply path), so
the two tools can never drift apart on what a valid rewrite target is.  It is
pure by construction: it takes already-observed facts (booleans and digests),
never a ``Path``, and touches no filesystem.

Diagnostic codes, evaluated in this fixed order:

- ``rewrite_target_missing`` — the target does not exist.
- ``rewrite_target_not_regular`` — the target exists but is not a regular file
  (symlink, directory, device, ...).
- ``rewrite_checksum_stale`` — the target is a regular file but its digest no
  longer matches the one the caller read.

``None`` means the target is valid for a rewrite.
"""

from __future__ import annotations

import hashlib

__all__ = ["classify_rewrite_target", "compute_checksum"]

REWRITE_TARGET_MISSING = "rewrite_target_missing"
REWRITE_TARGET_NOT_REGULAR = "rewrite_target_not_regular"
REWRITE_CHECKSUM_STALE = "rewrite_checksum_stale"


def compute_checksum(data: bytes) -> str:
    """Return the lowercase 64-char sha256 hex digest of ``data``.

    Args:
        data: The exact bytes to digest (no decoding, no normalisation).

    Returns:
        ``hashlib.sha256(data).hexdigest()``.
    """
    return hashlib.sha256(data).hexdigest()


def classify_rewrite_target(
    *,
    exists: bool,
    is_regular: bool,
    actual_checksum: str | None,
    expected_checksum: str,
) -> str | None:
    """Classify an observed rewrite target against its expected digest.

    Args:
        exists: Whether the target path exists.
        is_regular: Whether the target is a regular file (not a symlink,
            directory or other special file).
        actual_checksum: Digest of the bytes currently on disk, or ``None``
            when no digest could be observed.
        expected_checksum: Digest the caller read before proposing the rewrite.

    Returns:
        ``None`` when the target is valid, otherwise the first matching
        diagnostic code in the documented order.
    """
    if not exists:
        return REWRITE_TARGET_MISSING
    if not is_regular:
        return REWRITE_TARGET_NOT_REGULAR
    if actual_checksum != expected_checksum:
        return REWRITE_CHECKSUM_STALE
    return None
