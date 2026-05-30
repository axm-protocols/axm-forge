"""Tests for axm_edit.tools.list_dir — ListDirTool."""

from __future__ import annotations

from axm_edit.tools.list_dir import ListDirTool


class TestListDirTool:
    """Tests for the ListDirTool AXMTool wrapper."""

    def test_name(self) -> None:
        tool = ListDirTool()
        assert tool.name == "list_dir"

    def test_nonexistent_path(self) -> None:
        """Non-existent path returns an error."""
        result = ListDirTool().execute(path="/nonexistent/path/xyz_abc")
        assert result.success is False
        assert result.error is not None
        assert "not a directory" in result.error.lower()
