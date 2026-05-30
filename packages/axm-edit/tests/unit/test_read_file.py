"""Tests for axm_edit.tools.read_file — ReadFileTool."""

from __future__ import annotations

from axm_edit.tools.read_file import ReadFileTool


class TestReadFileTool:
    """Tests for the ReadFileTool AXMTool wrapper."""

    def test_name(self) -> None:
        tool = ReadFileTool()
        assert tool.name == "read_file"

    def test_bad_root(self) -> None:
        """Non-existent root directory returns error."""
        result = ReadFileTool().execute(path="/nonexistent/root", file="foo.py")
        assert result.success is False
        assert "not a directory" in (result.error or "").lower()
