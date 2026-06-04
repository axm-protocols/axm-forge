"""Tests for axm_edit.tools.batch_rollback — BatchRollbackTool."""

from __future__ import annotations

from axm_edit.tools.batch_rollback import BatchRollbackTool, _render_text


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


class TestRenderText:
    """Tests for the compact text rendering of a rollback outcome."""

    def test_success_lists_every_restored_file(self) -> None:
        text = _render_text(
            success=True,
            checkpoint="536af2b1c0ffee",
            files=["a.py", "b.py"],
            error=None,
        )
        assert text.startswith("batch_rollback | ✓ | 2 files restored from 536af2b")
        assert "a.py" in text
        assert "b.py" in text

    def test_success_singular_no_files(self) -> None:
        text = _render_text(success=True, checkpoint="deadbeef", files=[], error=None)
        assert "0 files restored from deadbee" in text

    def test_failure_surfaces_error_and_checkpoint(self) -> None:
        text = _render_text(
            success=False,
            checkpoint="deadbeef",
            files=[],
            error="Rollback failed",
        )
        assert text.startswith("batch_rollback | ✗ | Rollback failed")
        assert "(checkpoint deadbee)" in text
