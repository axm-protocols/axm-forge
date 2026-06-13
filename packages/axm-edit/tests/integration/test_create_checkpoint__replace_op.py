"""Integration tests for targeted checkpoint/rollback (AXM-1844).

These exercise the module-public ``create_checkpoint`` / ``rollback`` pair,
which snapshot only the paths a batch will touch and restore exactly those
paths on rollback -- with no global git checkout/clean/stash.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.core.checkpoint import create_checkpoint, rollback, snapshot_paths
from axm_edit.models.operations import Edit, ReplaceOp

pytestmark = pytest.mark.integration


def test_rollback_restores_modified_file_to_original_bytes(tmp_path: Path) -> None:
    """AC1, AC2: a replaced file is reverted to its original bytes."""
    target = tmp_path / "mod.txt"
    target.write_text("original")
    ops = [ReplaceOp(file="mod.txt", edits=[Edit(old="original", new="changed")])]

    snapshot = create_checkpoint(tmp_path, ops)
    target.write_text("changed")

    assert rollback(tmp_path, snapshot).ok is True
    assert target.read_text() == "original"


def test_rollback_leaves_unrelated_untracked_file_untouched(tmp_path: Path) -> None:
    """AC5: a path the batch never touched survives a rollback unchanged."""
    touched = tmp_path / "touched.txt"
    touched.write_text("before")
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_text("do-not-erase")
    ops = [ReplaceOp(file="touched.txt", edits=[Edit(old="before", new="after")])]

    snapshot = create_checkpoint(tmp_path, ops)
    touched.write_text("after")

    assert rollback(tmp_path, snapshot).ok is True
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
    assert rollback(tmp_path, snapshot).ok is True
    assert target.read_text() == "data"


# ---------------------------------------------------------------------------
# Merged from tests/unit/test_checkpoint.py (AXM-2031): resolved-path dedup of
# the snapshot path set. (module-level ``pytestmark`` already marks them.)
# ---------------------------------------------------------------------------


def test_aliased_paths_dedup_to_one_entry(tmp_path: Path) -> None:
    """AC1: two spellings of the same real file produce exactly one entry."""
    target = tmp_path / "a.py"
    target.write_text("x = 1\n")
    edit = [Edit(old="x = 1", new="x = 2")]
    ops = [
        ReplaceOp(file="a.py", edits=edit),
        ReplaceOp(file="./a.py", edits=edit),
    ]

    checkpoint = create_checkpoint(tmp_path, ops)

    assert len(snapshot_paths(checkpoint)) == 1


def test_single_spelling_unchanged(tmp_path: Path) -> None:
    """AC2: a single-spelling snapshot still records and restores the file."""
    target = tmp_path / "a.py"
    target.write_text("original\n")
    op = ReplaceOp(file="a.py", edits=[Edit(old="original", new="changed")])
    checkpoint = create_checkpoint(tmp_path, [op])
    target.write_text("changed\n")  # simulate the batch having edited the file

    result = rollback(tmp_path, checkpoint)

    assert snapshot_paths(checkpoint) == ["a.py"]
    assert target.read_text() == "original\n"
    assert result.ok
