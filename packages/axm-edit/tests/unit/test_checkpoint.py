"""Unit tests for rollback-as-strict-inverse and prune-only-batch-dirs.

Covers AXM-2031 F3 (pre-existing empty dir wrongly pruned) and F4 (partial
rollback silently swallowed).
"""

from __future__ import annotations

from pathlib import Path

from axm_edit.core.checkpoint import create_checkpoint, rollback, snapshot_paths
from axm_edit.models.operations import CreateOp, Edit, ReplaceOp


def test_rollback_preserves_preexisting_empty_dir(tmp_path: Path) -> None:
    """AC1: a pre-existing empty dir survives rollback of a CreateOp inside it."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()  # pre-existing, empty
    new_file = pkg / "new.py"
    op = CreateOp(file="pkg/new.py", content="x = 1\n")
    checkpoint = create_checkpoint(tmp_path, [op])
    new_file.write_text("x = 1\n")  # simulate the batch having created the file

    result = rollback(tmp_path, checkpoint)

    assert not new_file.exists()
    assert pkg.exists()  # pre-existing dir must NOT be pruned
    assert result.restored


def test_rollback_prunes_only_batch_created_dirs(tmp_path: Path) -> None:
    """AC1: a dir the batch created is pruned; pre-existing siblings untouched."""
    sibling = tmp_path / "existing"
    sibling.mkdir()  # pre-existing sibling, must survive
    gen = tmp_path / "gen"
    gen_file = gen / "x.py"
    op = CreateOp(file="gen/x.py", content="x = 1\n")
    checkpoint = create_checkpoint(tmp_path, [op])
    gen.mkdir()  # batch creates the dir
    gen_file.write_text("x = 1\n")  # and the file

    rollback(tmp_path, checkpoint)

    assert not gen_file.exists()
    assert not gen.exists()  # batch-created dir pruned
    assert sibling.exists()  # pre-existing sibling untouched


def test_rollback_returns_restored_and_unrestored(tmp_path: Path) -> None:
    """AC2: rollback reports restored paths via a result object, not a bool."""
    new_file = tmp_path / "new.py"
    op = CreateOp(file="new.py", content="x = 1\n")
    checkpoint = create_checkpoint(tmp_path, [op])
    new_file.write_text("x = 1\n")

    result = rollback(tmp_path, checkpoint)

    assert "new.py" in result.restored
    assert result.unrestored == []
    assert result.ok


def test_aliased_paths_dedup_to_one_entry(tmp_path: Path) -> None:
    """AC1: two spellings of the same real file produce exactly one entry."""
    target = tmp_path / "a.py"
    target.write_text("x = 1\n")
    ops = [
        ReplaceOp(file="a.py", edits=[Edit(old="x = 1", new="x = 2")]),
        ReplaceOp(file="./a.py", edits=[Edit(old="x = 2", new="x = 3")]),
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
