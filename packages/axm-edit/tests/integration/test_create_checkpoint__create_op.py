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

    assert rollback(tmp_path, snapshot) is True
    assert not created.exists()
