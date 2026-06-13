"""Integration test for targeted checkpoint/rollback of a deleted file.

Exercises the module-public ``create_checkpoint`` / ``rollback`` pair for a
batch-deleted file (AXM-1844).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.core.checkpoint import create_checkpoint, rollback
from axm_edit.models.operations import DeleteOp

pytestmark = pytest.mark.integration


def test_rollback_restores_batch_deleted_file(tmp_path: Path) -> None:
    """A file deleted by the batch is restored with its original content."""
    target = tmp_path / "gone.txt"
    target.write_text("keepme")
    ops = [DeleteOp(file="gone.txt")]

    snapshot = create_checkpoint(tmp_path, ops)
    target.unlink()

    assert rollback(tmp_path, snapshot).ok is True
    assert target.exists()
    assert target.read_text() == "keepme"
