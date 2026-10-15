"""One integration lock per git repository, shared by every AXM integrator.

Integrating an attempt (replaying its commits onto the lane, then
fast-forwarding the lane) and rolling an attempt back (removing its execution
worktree, re-verifying that none of its commits reached the lane) read and
write the same refs. Interleaved, a rollback can remove the worktree of an
attempt whose commits have just landed. Every such step therefore runs under
:func:`repository_lock` -- the warden and the tribunal ``dev.work.exec`` /
land graphs alike.

The lock is a protocol, not only this function: an advisory exclusive
``flock(2)`` on :data:`INTEGRATION_LOCK_NAME` inside the repository's
**common** git directory (``git rev-parse --git-common-dir``), so every
worktree of one repository contends for the same file and distinct
repositories never contend. The kernel releases it when its holder exits, so
a crashed holder leaves no stale lock behind. Any process that integrates into
a lane must take it the same way, whatever its language.
"""

from __future__ import annotations

import fcntl
import os
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Final

from axm_git.core.runner import run_git

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = [
    "INTEGRATION_LOCK_NAME",
    "RepositoryLockTimeoutError",
    "repository_lock",
    "repository_lock_path",
]

#: The lock file's name, inside the repository's common git directory.
#: Part of the cross-process protocol: never rename it without migrating
#: every holder at once.
INTEGRATION_LOCK_NAME: Final = "axm-integration.lock"
_POLL_SECONDS: Final = 0.05
_COMMON_DIR_ARGS: Final = ("rev-parse", "--path-format=absolute", "--git-common-dir")


class RepositoryLockTimeoutError(TimeoutError):
    """The repository lock was still held by another holder when the wait ran out."""


def repository_lock_path(repo_path: str | Path) -> Path | None:
    """Return the lock file of the repository holding *repo_path*.

    Every worktree of one repository resolves to the same path.

    Args:
        repo_path: Any directory inside a git repository or one of its
            worktrees.

    Returns:
        ``<common git dir>/axm-integration.lock``, or ``None`` when git
        cannot place *repo_path* in a repository.
    """
    try:
        proc = run_git(list(_COMMON_DIR_ARGS), Path(repo_path))
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = proc.stdout.strip() if proc.returncode == 0 else ""
    return Path(text) / INTEGRATION_LOCK_NAME if text else None


@contextmanager
def repository_lock(repo_path: str | Path, *, timeout: float) -> Iterator[Path]:
    """Hold the integration lock of *repo_path*'s repository for the block.

    Args:
        repo_path: Any directory inside the repository or one of its
            worktrees.
        timeout: Seconds to wait for another holder to release the lock
            (``0`` tries once).

    Yields:
        The lock file's path.

    Raises:
        ValueError: *repo_path* is not inside a git repository.
        RepositoryLockTimeoutError: another holder kept the lock past
            *timeout*.
    """
    path = repository_lock_path(repo_path)
    if path is None:
        raise ValueError(f"{repo_path} is not inside a git repository")
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        _acquire(fd, path, timeout)
        try:
            yield path
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _acquire(fd: int, path: Path, timeout: float) -> None:
    """Take the exclusive lock on *fd*, polling until *timeout* seconds elapse."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise RepositoryLockTimeoutError(
                    f"{path} still held after {timeout:g} s"
                ) from None
            time.sleep(_POLL_SECONDS)
        else:
            return
