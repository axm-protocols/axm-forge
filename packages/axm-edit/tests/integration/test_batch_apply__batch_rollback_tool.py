"""Integration tests wiring the snapshot through batch_apply + BatchRollbackTool.

AXM-1844: the engine snapshots every target path before apply and the
``batch_rollback`` tool restores exactly those paths.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.core.engine import batch_apply
from axm_edit.models.operations import CreateOp, DeleteOp, Edit, ReplaceOp
from axm_edit.tools.batch_rollback import BatchRollbackTool

pytestmark = pytest.mark.integration


def test_batch_rollback_restores_only_touched_paths(tmp_path: Path) -> None:
    """AC2, AC5: rollback reverts touched paths, leaves unrelated dirty files intact."""
    mod = tmp_path / "mod.txt"
    mod.write_text("orig")
    doomed = tmp_path / "doomed.txt"
    doomed.write_text("delete-me")
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_text("untouched")

    ops = [
        ReplaceOp(file="mod.txt", edits=[Edit(old="orig", new="edited")]),
        CreateOp(file="created.txt", content="fresh"),
        DeleteOp(file="doomed.txt"),
    ]

    result = batch_apply(tmp_path, ops)
    assert result.success is True
    assert result.checkpoint is not None
    assert (tmp_path / "created.txt").exists()
    assert not doomed.exists()
    assert mod.read_text().rstrip("\n") == "edited"

    tool = BatchRollbackTool()
    out = tool.execute(path=str(tmp_path), checkpoint=result.checkpoint)
    assert out.success is True

    # Touched paths reverted.
    assert mod.read_text() == "orig"
    assert not (tmp_path / "created.txt").exists()
    assert doomed.exists()
    assert doomed.read_text() == "delete-me"
    # Unrelated dirty file untouched.
    assert unrelated.read_text() == "untouched"
