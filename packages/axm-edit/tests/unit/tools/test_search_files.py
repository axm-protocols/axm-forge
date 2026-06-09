"""Tests for axm_edit.tools.search_files — SearchFilesTool."""

from __future__ import annotations

from axm_edit.tools.search_files import SearchFilesTool, _render_text


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


class TestRenderText:
    """Tests for the ``_render_text`` compact rendering helper."""

    def test_zero_matches(self) -> None:
        assert _render_text(matches=[], count=0, truncated=False) == (
            "search_files | 0 matches"
        )

    def test_truncation_flag_is_surfaced(self) -> None:
        """The TRUNCATED signal must appear in the text when the cap is hit."""
        matches: list[dict[str, object]] = [
            {"file": "a.py", "line": 1, "content": "hit"}
        ]
        text = _render_text(matches=matches, count=1, truncated=True)
        assert "TRUNCATED at 1" in text

    def test_singular_match_and_file(self) -> None:
        matches: list[dict[str, object]] = [
            {"file": "a.py", "line": 7, "content": "needle"}
        ]
        text = _render_text(matches=matches, count=1, truncated=False)
        assert text == "search_files | 1 match · 1 file\na.py\n  7: needle"
