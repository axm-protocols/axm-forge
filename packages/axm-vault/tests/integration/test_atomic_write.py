"""Integration tests for :func:`axm_vault.store.atomic_write`.

These hit the real filesystem via ``tmp_path`` to exercise the crash-safe
temp-file + ``os.replace`` rotation primitive (AC1, Task 4).
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from axm_vault.store import atomic_write


@pytest.mark.integration
def test_atomic_write_is_0600_under_permissive_umask(tmp_path: Path) -> None:
    """AC1, AC3: atomic_write yields mode 0600 even under a permissive umask."""
    target = tmp_path / "token.json"
    old_umask = os.umask(0)
    try:
        atomic_write(target, '{"refresh_token": "s3cr3t"}')
    finally:
        os.umask(old_umask)

    mode = stat.S_IMODE(target.stat().st_mode)
    assert mode == 0o600


@pytest.mark.integration
def test_atomic_write_creates_file(tmp_path: Path) -> None:
    """AC1: writing to a fresh path materializes the exact content."""
    target = tmp_path / "token.json"

    atomic_write(target, '{"refresh": "abc"}')

    assert target.read_text(encoding="utf-8") == '{"refresh": "abc"}'


@pytest.mark.integration
def test_atomic_write_overwrites_existing(tmp_path: Path) -> None:
    """AC1: an existing file is replaced in place, leaving no temp residue."""
    target = tmp_path / "token.json"
    target.write_text("stale", encoding="utf-8")

    atomic_write(target, "rotated")

    assert target.read_text(encoding="utf-8") == "rotated"
    assert [p.name for p in tmp_path.iterdir()] == ["token.json"]


@pytest.mark.integration
def test_atomic_write_fsyncs_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3: the parent directory is fsync-ed after os.replace (crash-safe).

    The rename is only durable once the directory entry is flushed to disk;
    atomic_write must open the parent dir read-only, fsync its fd and close
    it after the replace. We record fsync calls on directory fds and assert
    the parent directory was among them -- and the content stays correct.
    """
    target = tmp_path / "token.json"
    directory = str(tmp_path)

    real_open = os.open
    real_fsync = os.fsync
    dir_fds: set[int] = set()
    fsynced_dir = {"hit": False}

    def _tracking_open(
        path: object, flags: int, *args: object, **kwargs: object
    ) -> int:
        fd = real_open(path, flags, *args, **kwargs)
        if os.path.isdir(path) and str(path) == directory:
            dir_fds.add(fd)
        return fd

    def _tracking_fsync(fd: int) -> None:
        if fd in dir_fds:
            fsynced_dir["hit"] = True
        real_fsync(fd)

    monkeypatch.setattr(os, "open", _tracking_open)
    monkeypatch.setattr(os, "fsync", _tracking_fsync)

    atomic_write(target, '{"refresh": "durable"}')

    assert fsynced_dir["hit"] is True
    assert target.read_text(encoding="utf-8") == '{"refresh": "durable"}'
