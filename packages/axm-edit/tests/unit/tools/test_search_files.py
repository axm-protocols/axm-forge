"""Tests for axm_edit.tools.search_files — SearchFilesTool."""

from __future__ import annotations

from pathlib import Path

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

    def test_text_field_groups_matches_by_file(self, tmp_path: Path) -> None:
        """A successful search exposes a compact ``text`` grouped by file."""
        (tmp_path / "a.py").write_text("alpha\nbeta alpha\n", encoding="utf-8")
        (tmp_path / "b.py").write_text("gamma\nalpha\n", encoding="utf-8")

        result = SearchFilesTool().execute(
            path=str(tmp_path), pattern="alpha", include=["*.py"]
        )

        assert result.success is True
        assert result.text is not None
        # Header carries count and file count; bodies carry path + line + content.
        assert "3 matches" in result.text
        assert "2 files" in result.text
        assert "a.py" in result.text
        assert "b.py" in result.text
        assert "1: alpha" in result.text
        assert "2: beta alpha" in result.text

    def test_text_reflects_every_data_match(self, tmp_path: Path) -> None:
        """No match is lost: each data match appears in ``text`` verbatim."""
        (tmp_path / "f.py").write_text("x\nfind me\nfind me too\n", encoding="utf-8")

        result = SearchFilesTool().execute(
            path=str(tmp_path), pattern="find", include=["*.py"]
        )

        for match in result.data["matches"]:
            assert f"{match['line']}: {match['content']}" in (result.text or "")


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
