"""Real-filesystem tests for the durable whole-file replacement primitive."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from axm_edit.core.atomic_write import atomic_replace

pytestmark = pytest.mark.integration


def _temp_siblings(directory: Path) -> list[Path]:
    return [p for p in directory.iterdir() if p.name.endswith(".axmtmp")]


def test_replacement_writes_the_exact_bytes_and_keeps_the_mode(tmp_path: Path) -> None:
    """AC2: the target holds the new bytes and keeps its original mode bits."""
    target = tmp_path / "mod.py"
    target.write_bytes(b"old content")
    target.chmod(0o640)

    atomic_replace(target, b"brand new content")

    assert target.read_bytes() == b"brand new content"
    assert stat.S_IMODE(target.stat().st_mode) == 0o640


def test_no_temp_sibling_survives_a_success(tmp_path: Path) -> None:
    """AC2: after a successful replace the directory holds only the target."""
    target = tmp_path / "mod.py"
    target.write_bytes(b"old")

    atomic_replace(target, b"new")

    assert sorted(p.name for p in tmp_path.iterdir()) == ["mod.py"]


def test_a_failing_os_replace_leaves_the_original_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3: the OSError propagates, the original bytes stay, no temp sibling leaks."""
    target = tmp_path / "mod.py"
    target.write_bytes(b"original bytes")

    def _boom(src: object, dst: object) -> None:
        raise OSError("replace refused")

    monkeypatch.setattr(os, "replace", _boom)

    with pytest.raises(OSError):
        atomic_replace(target, b"never written")

    assert target.read_bytes() == b"original bytes"
    assert _temp_siblings(tmp_path) == []


def test_file_and_directory_are_both_fsynced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC4: at least two distinct descriptors are fsynced (temp file + directory)."""
    target = tmp_path / "mod.py"
    target.write_bytes(b"old")
    real_fsync = os.fsync
    recorded: list[int] = []

    def _spy(fd: int) -> None:
        recorded.append(fd)
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", _spy)

    atomic_replace(target, b"new")

    assert len(set(recorded)) >= 2


def test_an_unsupported_directory_fsync_is_tolerated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC4: a directory fsync raising OSError does not fail the replacement."""
    target = tmp_path / "mod.py"
    target.write_bytes(b"old")
    real_fsync = os.fsync

    def _picky(fd: int) -> None:
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError("directory fsync unsupported")
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", _picky)

    atomic_replace(target, b"fresh bytes")

    assert target.read_bytes() == b"fresh bytes"
