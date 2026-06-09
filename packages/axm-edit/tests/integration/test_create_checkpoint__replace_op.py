"""Integration tests for targeted checkpoint/rollback (AXM-1844).

These exercise the module-public ``create_checkpoint`` / ``rollback`` pair,
which snapshot only the paths a batch will touch and restore exactly those
paths on rollback -- with no global git checkout/clean/stash.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.core import checkpoint as checkpoint_mod
from axm_edit.core.checkpoint import create_checkpoint, rollback
from axm_edit.models.operations import CreateOp, DeleteOp, Edit, ReplaceOp

pytestmark = pytest.mark.integration


def test_rollback_restores_modified_file_to_original_bytes(tmp_path: Path) -> None:
    """AC1, AC2: a replaced file is reverted to its original bytes."""
    target = tmp_path / "mod.txt"
    target.write_text("original")
    ops = [ReplaceOp(file="mod.txt", edits=[Edit(old="original", new="changed")])]

    snapshot = create_checkpoint(tmp_path, ops)
    target.write_text("changed")

    assert rollback(tmp_path, snapshot) is True
    assert target.read_text() == "original"


def test_rollback_removes_batch_created_file(tmp_path: Path) -> None:
    """AC2: a file that did not exist before the batch is removed on rollback."""
    ops = [CreateOp(file="new.txt", content="hello")]

    snapshot = create_checkpoint(tmp_path, ops)
    created = tmp_path / "new.txt"
    created.write_text("hello")

    assert rollback(tmp_path, snapshot) is True
    assert not created.exists()


def test_rollback_restores_batch_deleted_file(tmp_path: Path) -> None:
    """AC2: a file deleted by the batch is restored with its original content."""
    target = tmp_path / "gone.txt"
    target.write_text("keepme")
    ops = [DeleteOp(file="gone.txt")]

    snapshot = create_checkpoint(tmp_path, ops)
    target.unlink()

    assert rollback(tmp_path, snapshot) is True
    assert target.exists()
    assert target.read_text() == "keepme"


def test_rollback_leaves_unrelated_untracked_file_untouched(tmp_path: Path) -> None:
    """AC5: a path the batch never touched survives a rollback unchanged."""
    touched = tmp_path / "touched.txt"
    touched.write_text("before")
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_text("do-not-erase")
    ops = [ReplaceOp(file="touched.txt", edits=[Edit(old="before", new="after")])]

    snapshot = create_checkpoint(tmp_path, ops)
    touched.write_text("after")

    assert rollback(tmp_path, snapshot) is True
    assert unrelated.exists()
    assert unrelated.read_text() == "do-not-erase"
    assert touched.read_text() == "before"


def test_create_checkpoint_in_non_git_dir_still_snapshots(tmp_path: Path) -> None:
    """AC4: a checkpoint is produced even when the dir is not a git repo."""
    target = tmp_path / "plain.txt"
    target.write_text("data")
    assert not (tmp_path / ".git").exists()
    ops = [ReplaceOp(file="plain.txt", edits=[Edit(old="data", new="data2")])]

    snapshot = create_checkpoint(tmp_path, ops)

    assert snapshot is not None
    # The snapshot must cover the target path so rollback can restore it.
    target.write_text("data2")
    assert rollback(tmp_path, snapshot) is True
    assert target.read_text() == "data"


def test_no_git_global_commands_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3: no global git checkout/clean/stash is invoked by checkpoint/rollback."""
    calls: list[list[str]] = []

    def _spy(cmd: list[str], *args: object, **kwargs: object) -> object:
        calls.append(list(cmd))
        raise AssertionError(f"subprocess invoked: {cmd}")

    monkeypatch.setattr(checkpoint_mod.subprocess, "run", _spy)

    target = tmp_path / "f.txt"
    target.write_text("v1")
    ops = [ReplaceOp(file="f.txt", edits=[Edit(old="v1", new="v2")])]

    snapshot = create_checkpoint(tmp_path, ops)
    target.write_text("v2")
    rollback(tmp_path, snapshot)

    assert calls == []
