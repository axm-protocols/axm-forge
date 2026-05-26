"""Git checkpoint and rollback for atomic batch edits.

Creates a lightweight git stash before applying edits so the agent
can rollback if the result is unsatisfactory.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def create_checkpoint(root: Path) -> str | None:
    """Create a git stash checkpoint.

    Args:
        root: Project root directory.

    Returns:
        The stash commit SHA, or ``None`` if not a git repo or nothing
        to stash.
    """
    git_dir = root / ".git"
    if not git_dir.exists():
        return None

    try:
        result = subprocess.run(
            ["git", "stash", "create", "-m", "axm-edit checkpoint"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        sha = result.stdout.strip()
        return sha if sha else None
    except OSError:
        return None


def rollback(root: Path, checkpoint: str) -> bool:
    """Rollback to a previous checkpoint.

    Restores the working tree to the state captured by
    :func:`create_checkpoint`.

    Args:
        root: Project root directory.
        checkpoint: The stash SHA returned by ``create_checkpoint``.

    Returns:
        ``True`` if rollback succeeded.
    """
    try:
        # Reset tracked files
        subprocess.run(
            ["git", "checkout", "--", "."],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        # Remove untracked files created by batch_edit
        subprocess.run(
            ["git", "clean", "-fd"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        # Re-apply the stashed state
        if checkpoint:
            subprocess.run(
                ["git", "stash", "apply", checkpoint],
                cwd=root,
                capture_output=True,
                text=True,
                check=True,
            )
        return True
    except (subprocess.CalledProcessError, OSError):
        return False
