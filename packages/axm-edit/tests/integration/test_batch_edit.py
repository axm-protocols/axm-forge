"""Integration tests for axm_edit.tools.batch_edit — BatchEditTool (real I/O)."""

from __future__ import annotations

from pathlib import Path

from axm_edit.tools.batch_edit import BatchEditTool


class TestBatchEditTool:
    """Tests for the BatchEditTool AXMTool wrapper."""

    def test_execute_replace(self, tmp_project: Path) -> None:
        tool = BatchEditTool()
        result = tool.execute(
            path=str(tmp_project),
            operations=[
                {
                    "op": "replace",
                    "file": "src/foo.py",
                    "edits": [{"line": 1, "old": "import os", "new": "import pathlib"}],
                },
            ],
        )
        assert result.success
        assert result.data["applied"] == 1

    def test_execute_create(self, tmp_project: Path) -> None:
        tool = BatchEditTool()
        result = tool.execute(
            path=str(tmp_project),
            operations=[
                {"op": "create", "file": "new.py", "content": "hello\n"},
            ],
        )
        assert result.success
        assert (tmp_project / "new.py").exists()

    def test_execute_validation_error(self, tmp_project: Path) -> None:
        tool = BatchEditTool()
        result = tool.execute(
            path=str(tmp_project),
            operations=[
                {
                    "op": "replace",
                    "file": "src/foo.py",
                    "edits": [{"line": 1, "old": "WRONG", "new": "b"}],
                },
            ],
        )
        assert not result.success
        assert result.error is not None

    def test_execute_unknown_op(self, tmp_project: Path) -> None:
        tool = BatchEditTool()
        result = tool.execute(
            path=str(tmp_project),
            operations=[{"op": "unknown", "file": "foo.py"}],
        )
        assert not result.success
        assert "Unknown" in (result.error or "")
