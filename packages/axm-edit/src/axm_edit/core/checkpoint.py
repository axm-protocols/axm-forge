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

from axm_edit.models.operations import RollbackResult

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
    created_dirs: set[str] = set()
    for op in operations:
        target = _resolve_within(root, op.file)
        if target is None:
            continue
        # Key the dedup on the canonical resolved-within path, not the raw
        # spelling: "a.py" and "./a.py" name the same file and must collapse
        # to a single entry. The canonical key is also what rollback re-resolves.
        rel = target.relative_to(root).as_posix()
        if rel in entries:
            continue
        if target.is_file():
            entries[rel] = base64.b64encode(target.read_bytes()).decode("ascii")
        else:
            entries[rel] = None
            created_dirs |= _ancestors_to_create(root, target)
    return json.dumps(
        {
            "version": _SNAPSHOT_VERSION,
            "entries": entries,
            "created_dirs": sorted(created_dirs),
        }
    )


def _ancestors_to_create(root: Path, target: Path) -> set[str]:
    """Relative paths of *target*'s ancestor dirs that do not yet exist.

    These are exactly the directories a ``mkdir(parents=True)`` for *target*
    will bring into being — the only directories rollback is allowed to prune.
    Stops at *root*; a pre-existing directory is never included.
    """
    pending: set[str] = set()
    current = target.parent
    while current != root and root in current.parents:
        if current.exists():
            break
        pending.add(current.relative_to(root).as_posix())
        current = current.parent
    return pending


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


def rollback(root: Path, checkpoint: str) -> RollbackResult:
    """Restore exactly the paths captured by *checkpoint* to their prior state.

    Rollback is a *strict inverse* of the batch and best-effort: for each
    snapshotted path a file that existed is rewritten with its original bytes,
    a file that did not exist before is removed, and only the directories the
    batch itself created (recorded in the snapshot) are pruned — a
    pre-existing directory is never removed. Every captured path is attempted
    even if an earlier one fails, so a partial rollback is fully reported. No
    git command is run.

    Args:
        root: Project root directory.
        checkpoint: The JSON snapshot returned by :func:`create_checkpoint`.

    Returns:
        A :class:`~axm_edit.models.operations.RollbackResult` listing the
        paths restored and those that could not be restored. ``RollbackResult.ok``
        is ``True`` only on a well-formed snapshot with no per-path failure;
        a malformed snapshot yields ``valid=False``.
    """
    root = root.resolve()
    try:
        payload = json.loads(checkpoint)
        entries = payload["entries"]
    except (ValueError, TypeError, KeyError):
        return RollbackResult(valid=False)
    if not isinstance(entries, dict):
        return RollbackResult(valid=False)

    created_dirs = _read_created_dirs(payload)
    restored: list[str] = []
    unrestored: list[str] = []
    for rel, encoded in entries.items():
        target = _resolve_within(root, rel)
        if target is None:
            continue
        try:
            _restore_one(target, encoded, root, created_dirs)
            restored.append(rel)
        except OSError:
            unrestored.append(rel)
    return RollbackResult(restored=restored, unrestored=unrestored)


def _read_created_dirs(payload: object) -> set[str]:
    """Read the batch-created directory set from a snapshot payload."""
    if not isinstance(payload, dict):
        return set()
    raw = payload.get("created_dirs")
    if not isinstance(raw, list):
        return set()
    return {item for item in raw if isinstance(item, str)}


def _restore_one(
    target: Path, encoded: str | None, root: Path, created_dirs: set[str]
) -> None:
    """Restore a single path to its captured state."""
    if encoded is None:
        # Did not exist before the batch — remove whatever is there now,
        # then prune only the directories the batch itself created for it.
        target.unlink(missing_ok=True)
        _prune_empty_dirs(target.parent, root, created_dirs)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(base64.b64decode(encoded))


def _prune_empty_dirs(start: Path, root: Path, created_dirs: set[str]) -> None:
    """Remove empty directories the batch created, walking up from *start*.

    Only directories listed in *created_dirs* (the dirs the batch's
    ``mkdir(parents=True)`` brought into being) are candidates — a
    pre-existing directory is never removed even when empty. ``rmdir`` only
    succeeds on an empty directory, so a batch-created dir that still holds
    other files is also left intact. Stops at the first non-candidate or
    non-empty directory, or at *root*.
    """
    current = start
    while current != root and root in current.parents:
        rel = current.relative_to(root).as_posix()
        if rel not in created_dirs:
            return
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent
