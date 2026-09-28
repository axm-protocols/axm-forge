"""The repository lock over real git repositories, worktrees and processes."""

from __future__ import annotations

import fcntl
import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from axm_git.core.lock import (
    INTEGRATION_LOCK_NAME,
    RepositoryLockTimeoutError,
    repository_lock,
    repository_lock_path,
)
from axm_git.core.runner import run_git

pytestmark = pytest.mark.integration

_HOLDER = """
import sys
from axm_git.core.lock import repository_lock
with repository_lock(sys.argv[1], timeout=10):
    print("held", flush=True)
    sys.stdin.readline()
"""


@pytest.fixture
def linked(tmp_git_repo: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A second worktree of ``tmp_git_repo``, outside its working tree."""
    target = tmp_path_factory.mktemp("worktrees") / "linked"
    added = run_git(["worktree", "add", "-q", "--detach", str(target)], tmp_git_repo)
    assert added.returncode == 0, added.stderr
    return target


@contextmanager
def _held_by_another_process(repo: Path) -> Iterator[None]:
    """Hold the lock of *repo* from a child interpreter for the block."""
    child = subprocess.Popen(
        [sys.executable, "-c", _HOLDER, str(repo)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)},
    )
    assert child.stdin is not None
    assert child.stdout is not None
    try:
        assert child.stdout.readline().strip() == "held"
        yield
    finally:
        child.stdin.close()
        child.wait(timeout=30)
        child.stdout.close()


def test_every_worktree_of_a_repository_shares_one_lock_file(
    tmp_git_repo: Path, linked: Path
) -> None:
    lane = repository_lock_path(tmp_git_repo)

    assert lane is not None
    assert lane.name == INTEGRATION_LOCK_NAME
    assert lane.parent.resolve() == (tmp_git_repo / ".git").resolve()
    assert repository_lock_path(str(linked)) == lane


def test_a_second_holder_times_out_while_the_first_holds_it(
    tmp_git_repo: Path, linked: Path
) -> None:
    """The lane and a worktree of it contend: one holder at a time."""
    with repository_lock(tmp_git_repo, timeout=0) as held:
        with pytest.raises(RepositoryLockTimeoutError, match="still held"):
            with repository_lock(linked, timeout=0.1):
                pass  # pragma: no cover - never acquired
        assert held.exists()

    with repository_lock(linked, timeout=0):
        pass  # released on exit: acquired at once


def test_another_process_holding_the_lock_excludes_this_one(
    tmp_git_repo: Path, linked: Path
) -> None:
    with _held_by_another_process(linked):
        with pytest.raises(RepositoryLockTimeoutError):
            with repository_lock(tmp_git_repo, timeout=0.1):
                pass  # pragma: no cover - never acquired

    with repository_lock(tmp_git_repo, timeout=5):
        pass  # the child released it when it exited


def test_a_raw_flock_on_the_named_file_excludes_the_lock(tmp_git_repo: Path) -> None:
    """Any holder following the protocol (e.g. the warden) contends for it."""
    path = tmp_git_repo / ".git" / INTEGRATION_LOCK_NAME
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RepositoryLockTimeoutError):
            with repository_lock(tmp_git_repo, timeout=0):
                pass  # pragma: no cover - never acquired
    finally:
        os.close(fd)

    with repository_lock(tmp_git_repo, timeout=0):
        pass  # closing the foreign descriptor released it


def test_distinct_repositories_never_contend(
    tmp_git_repo: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    other = tmp_path_factory.mktemp("other")
    run_git(["init", "-q"], other)

    with repository_lock(tmp_git_repo, timeout=0):
        with repository_lock(other, timeout=0) as held:
            assert held.parent.resolve() == (other / ".git").resolve()


def test_a_path_outside_any_repository_has_no_lock(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    outside = tmp_path_factory.mktemp("plain")

    assert repository_lock_path(outside) is None
    with pytest.raises(ValueError, match="not inside a git repository"):
        with repository_lock(outside, timeout=0):
            pass  # pragma: no cover - never acquired
