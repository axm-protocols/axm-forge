"""Tests for axm_edit.tools.search_files — SearchFilesTool."""

from __future__ import annotations

from axm_edit.tools.search_files import SearchFilesTool


class TestSearchFilesTool:
    """Tests for the SearchFilesTool AXMTool wrapper."""

    def test_name(self) -> None:
        tool = SearchFilesTool()
        assert tool.name == "search_files"

    def test_bad_root(self) -> None:
        """Non-existent root directory returns error."""
        result = SearchFilesTool().execute(path="/nonexistent/root", pattern="foo")
        assert result.success is False
        assert "not a directory" in (result.error or "").lower()
