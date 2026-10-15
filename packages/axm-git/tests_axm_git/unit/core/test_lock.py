"""Unit contracts of the repository lock: resolution and polling, no real I/O."""

from __future__ import annotations

import fcntl
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from axm_git.core import lock
from axm_git.core.lock import (
    INTEGRATION_LOCK_NAME,
    RepositoryLockTimeoutError,
    repository_lock,
    repository_lock_path,
)


def _completed(returncode: int, stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["git"], returncode, stdout=stdout, stderr="")


def test_the_lock_name_is_the_one_the_warden_documents() -> None:
    """A warden holding its own lock and a graph holding this one exclude each other."""
    assert INTEGRATION_LOCK_NAME == "axm-integration.lock"


def test_the_lock_timeout_is_a_timeout_error() -> None:
    assert issubclass(RepositoryLockTimeoutError, TimeoutError)


def test_the_lock_lives_in_the_common_git_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_git = MagicMock(return_value=_completed(0, "/repo/.git\n"))
    monkeypatch.setattr(lock, "run_git", run_git)

    assert repository_lock_path("/repo/linked") == Path(
        "/repo/.git", INTEGRATION_LOCK_NAME
    )
    run_git.assert_called_once_with(
        ["rev-parse", "--path-format=absolute", "--git-common-dir"],
        Path("/repo/linked"),
    )


@pytest.mark.parametrize(
    "outcome",
    [
        _completed(128, ""),
        _completed(0, "  \n"),
        FileNotFoundError("/nowhere"),
        subprocess.TimeoutExpired(["git"], 30.0),
    ],
    ids=["git-fails", "blank-output", "missing-dir", "git-times-out"],
)
def test_a_path_git_cannot_place_has_no_lock(
    monkeypatch: pytest.MonkeyPatch,
    outcome: subprocess.CompletedProcess[str] | Exception,
) -> None:
    run_git = MagicMock()
    if isinstance(outcome, Exception):
        run_git.side_effect = outcome
    else:
        run_git.return_value = outcome
    monkeypatch.setattr(lock, "run_git", run_git)

    assert repository_lock_path("/nowhere") is None


def test_locking_outside_git_raises_value_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(lock, "repository_lock_path", lambda _path: None)

    with pytest.raises(ValueError, match="/nowhere is not inside a git repository"):
        with repository_lock("/nowhere", timeout=0):
            pass  # pragma: no cover - never acquired


@pytest.fixture
def fake_fd(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Resolve to a fixed lock path and stub the lock module's OS seams.

    The ``os`` / ``fcntl`` / ``time`` names are swapped on the lock module
    only, so the real modules stay untouched for the rest of the process.
    """
    monkeypatch.setattr(
        lock, "repository_lock_path", lambda _path: Path("/repo/.git/lock")
    )
    fake = MagicMock()
    fake.open.return_value = 7
    monkeypatch.setattr(lock, "os", fake)
    monkeypatch.setattr(
        lock, "time", SimpleNamespace(monotonic=time.monotonic, sleep=fake.sleep)
    )
    monkeypatch.setattr(
        lock,
        "fcntl",
        SimpleNamespace(
            LOCK_EX=fcntl.LOCK_EX,
            LOCK_NB=fcntl.LOCK_NB,
            LOCK_UN=fcntl.LOCK_UN,
            flock=fake.flock,
        ),
    )
    return fake


def test_a_held_lock_is_polled_until_released(fake_fd: MagicMock) -> None:
    fake_fd.flock.side_effect = [BlockingIOError, BlockingIOError, None, None]

    with repository_lock("/repo", timeout=60) as held:
        assert held == Path("/repo/.git/lock")

    assert fake_fd.sleep.call_count == 2
    assert fake_fd.flock.call_args_list[-1].args == (7, fcntl.LOCK_UN)
    fake_fd.close.assert_called_once_with(7)


def test_a_lock_still_held_at_the_deadline_times_out(fake_fd: MagicMock) -> None:
    fake_fd.flock.side_effect = BlockingIOError

    with pytest.raises(RepositoryLockTimeoutError, match="still held after 0 s"):
        with repository_lock("/repo", timeout=0):
            pass  # pragma: no cover - never acquired

    fake_fd.sleep.assert_not_called()
    fake_fd.close.assert_called_once_with(7)
