"""Tests for axm_edit.tools.batch_rollback — BatchRollbackTool."""

from __future__ import annotations

from axm_edit.tools.batch_rollback import BatchRollbackTool


class TestBatchRollbackTool:
    """Tests for the BatchRollbackTool AXMTool wrapper."""

    def test_name(self) -> None:
        tool = BatchRollbackTool()
        assert tool.name == "batch_rollback"

    def test_no_checkpoint(self) -> None:
        tool = BatchRollbackTool()
        result = tool.execute(path=".")
        assert not result.success
        assert "checkpoint is required" in (result.error or "")

    def test_bad_path(self) -> None:
        tool = BatchRollbackTool()
        result = tool.execute(path="/nonexistent", checkpoint="abc123")
        assert not result.success
