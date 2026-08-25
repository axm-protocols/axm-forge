"""Integration test for targeted checkpoint/rollback of a created file.

Exercises the module-public ``create_checkpoint`` / ``rollback`` pair for a
batch-created file (AXM-1844).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.core.checkpoint import create_checkpoint, rollback
from axm_edit.models.operations import CreateOp

pytestmark = pytest.mark.integration


def test_rollback_removes_batch_created_file(tmp_path: Path) -> None:
    """A file that did not exist before the batch is removed on rollback."""
    ops = [CreateOp(file="new.txt", content="hello")]

    snapshot = create_checkpoint(tmp_path, ops)
    created = tmp_path / "new.txt"
    created.write_text("hello")

    assert rollback(tmp_path, snapshot).ok is True
    assert not created.exists()


# ---------------------------------------------------------------------------
# Merged from tests/unit/test_checkpoint.py (AXM-2031): rollback as a strict
# inverse -- pre-existing dirs survive, batch-created dirs are pruned, and the
# result object reports restored paths. (module ``pytestmark`` marks them.)
# ---------------------------------------------------------------------------


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
