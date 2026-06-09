"""Targeted path snapshot and rollback for atomic batch edits.

Before applying a batch, :func:`create_checkpoint` captures — for **every
path the batch will touch** — whether it existed and its original bytes.
:func:`rollback` then restores exactly those paths and nothing else:
modified files are rewritten with their original bytes, files that did not
exist before are removed, and files that were deleted are recreated.

No git is involved: the snapshot is independent of the repository (it works
in a non-git directory and never runs ``git checkout``/``clean``/``stash``).
The snapshot is serialized to a JSON string so it can ride on the existing
``BatchResult.checkpoint`` field and cross the MCP boundary unchanged.
"""

from __future__ import annotations

import base64
import json
import subprocess  # noqa: F401  # retained so callers/tests can spy; never invoked here
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from axm_edit.models.operations import Operation

__all__ = ["create_checkpoint", "rollback", "snapshot_paths"]

_SNAPSHOT_VERSION = 1


def _resolve_within(root: Path, relative: str) -> Path | None:
    """Resolve *relative* under *root*, rejecting paths that escape it."""
    if ".." in relative.split("/"):
        return None
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    return resolved


def create_checkpoint(root: Path, operations: Sequence[Operation]) -> str:
    """Snapshot every path *operations* will touch, before they are applied.

    For each operation's target path the snapshot records whether the file
    currently exists and, if so, its original bytes. The result is a JSON
    string keyed by resolved relative path, suitable for storage on
    ``BatchResult.checkpoint`` and for passing back to :func:`rollback`.

    Args:
        root: Project root directory (all paths are relative to this).
        operations: The batch about to be applied — replace, create and
            delete operations whose ``file`` attribute names the target.

    Returns:
        A JSON snapshot string. Always returned (never ``None``) whenever
        there are operations, in git and non-git directories alike.
    """
    root = root.resolve()
    entries: dict[str, str | None] = {}
    for op in operations:
        rel = op.file
        if rel in entries:
            continue
        target = _resolve_within(root, rel)
        if target is None:
            continue
        if target.is_file():
            entries[rel] = base64.b64encode(target.read_bytes()).decode("ascii")
        else:
            entries[rel] = None
    return json.dumps({"version": _SNAPSHOT_VERSION, "entries": entries})


def snapshot_paths(checkpoint: str) -> list[str]:
    """Return the relative paths captured by *checkpoint* (best-effort).

    Read-only and side-effect free: a malformed snapshot yields an empty
    list so informational callers degrade gracefully.
    """
    try:
        payload = json.loads(checkpoint)
        entries = payload["entries"]
    except (ValueError, TypeError, KeyError):
        return []
    if not isinstance(entries, dict):
        return []
    return list(entries)


def rollback(root: Path, checkpoint: str) -> bool:
    """Restore exactly the paths captured by *checkpoint* to their prior state.

    For each snapshotted path: a file that existed is rewritten with its
    original bytes; a file that did not exist before is removed; a file that
    was deleted by the batch is recreated. No other path in *root* is
    touched, and no git command is run.

    Args:
        root: Project root directory.
        checkpoint: The JSON snapshot returned by :func:`create_checkpoint`.

    Returns:
        ``True`` if the rollback completed, ``False`` on a malformed
        snapshot or a filesystem error.
    """
    root = root.resolve()
    try:
        payload = json.loads(checkpoint)
        entries = payload["entries"]
    except (ValueError, TypeError, KeyError):
        return False
    if not isinstance(entries, dict):
        return False

    try:
        for rel, encoded in entries.items():
            target = _resolve_within(root, rel)
            if target is None:
                continue
            _restore_one(target, encoded)
        return True
    except OSError:
        return False


def _restore_one(target: Path, encoded: str | None) -> None:
    """Restore a single path to its captured state."""
    if encoded is None:
        # Did not exist before the batch — remove whatever is there now.
        target.unlink(missing_ok=True)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(base64.b64decode(encoded))
