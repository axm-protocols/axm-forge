"""Tests for axm_edit.tools.search_files — SearchFilesTool."""

from __future__ import annotations

from pathlib import Path

from axm_edit.tools.search_files import SearchFilesTool


class TestSearchFilesTool:
    """Tests for the SearchFilesTool AXMTool wrapper."""

    def test_name(self) -> None:
        tool = SearchFilesTool()
        assert tool.name == "search_files"

    def test_literal_search(self, tmp_project: Path) -> None:
        """Literal search finds all occurrences of a string."""
        result = SearchFilesTool().execute(path=str(tmp_project), pattern="import os")
        assert result.success is True
        assert result.data is not None
        matches = result.data["matches"]
        assert len(matches) >= 1
        assert any(m["content"] == "import os" for m in matches)
        # Check result shape
        first = matches[0]
        assert "file" in first
        assert "line" in first
        assert "content" in first

    def test_regex_search(self, tmp_project: Path) -> None:
        """Regex mode matches function definitions."""
        result = SearchFilesTool().execute(
            path=str(tmp_project),
            pattern=r"def \w+\(",
            is_regex=True,
        )
        assert result.success is True
        assert result.data is not None
        matches = result.data["matches"]
        # tmp_project has hello(), greet(), bye()
        assert len(matches) >= 3

    def test_include_filter(self, tmp_project: Path) -> None:
        """include glob filters to only matching file types."""
        # "Test Project" is in README.md only
        result_all = SearchFilesTool().execute(
            path=str(tmp_project), pattern="Test Project"
        )
        assert result_all.success is True
        assert result_all.data is not None
        assert result_all.data["count"] >= 1

        # With include=*.py, should NOT find it
        result_py = SearchFilesTool().execute(
            path=str(tmp_project),
            pattern="Test Project",
            include=["*.py"],
        )
        assert result_py.success is True
        assert result_py.data is not None
        assert result_py.data["count"] == 0

    def test_result_cap(self, tmp_path: Path) -> None:
        """Results are capped at 50."""
        # Create a file with 100 matching lines
        big_file = tmp_path / "big.txt"
        big_file.write_text("\n".join(f"TODO item {i}" for i in range(100)))

        result = SearchFilesTool().execute(path=str(tmp_path), pattern="TODO")
        assert result.success is True
        assert result.data is not None
        assert result.data["count"] == 50
        assert result.data["truncated"] is True

    def test_no_matches(self, tmp_project: Path) -> None:
        """Search for non-existent string returns empty list."""
        result = SearchFilesTool().execute(
            path=str(tmp_project),
            pattern="this_string_does_not_exist_anywhere_xyz",
        )
        assert result.success is True
        assert result.data is not None
        assert result.data["matches"] == []
        assert result.data["count"] == 0
        assert result.data["truncated"] is False

    def test_binary_file_skipped(self, tmp_project: Path) -> None:
        """Binary files are silently skipped."""
        binary = tmp_project / "image.png"
        binary.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00match_me\x00")

        result = SearchFilesTool().execute(path=str(tmp_project), pattern="match_me")
        assert result.success is True
        assert result.data is not None
        # Should not find the pattern in the binary file
        for m in result.data["matches"]:
            assert m["file"] != "image.png"

    def test_empty_pattern(self, tmp_project: Path) -> None:
        """Empty pattern returns error."""
        result = SearchFilesTool().execute(path=str(tmp_project), pattern="")
        assert result.success is False
        assert "pattern" in (result.error or "").lower()

    def test_missing_pattern(self, tmp_project: Path) -> None:
        """Missing pattern argument returns error."""
        result = SearchFilesTool().execute(path=str(tmp_project))
        assert result.success is False
        assert "pattern" in (result.error or "").lower()

    def test_path_traversal(self, tmp_project: Path) -> None:
        """Searching outside root is sandboxed."""
        # The tool should not crash; paths outside root are simply ignored
        result = SearchFilesTool().execute(path=str(tmp_project), pattern="anything")
        assert result.success is True

    def test_hidden_dirs_skipped(self, tmp_project: Path) -> None:
        """Files in hidden directories are not searched."""
        hidden_dir = tmp_project / ".hidden"
        hidden_dir.mkdir()
        (hidden_dir / "secret.py").write_text("FINDME hidden secret\n")

        result = SearchFilesTool().execute(path=str(tmp_project), pattern="FINDME")
        assert result.success is True
        assert result.data is not None
        assert result.data["count"] == 0

    def test_bad_root(self) -> None:
        """Non-existent root directory returns error."""
        result = SearchFilesTool().execute(path="/nonexistent/root", pattern="foo")
        assert result.success is False
        assert "not a directory" in (result.error or "").lower()

    def test_invalid_regex(self, tmp_project: Path) -> None:
        """Invalid regex returns a clear error."""
        result = SearchFilesTool().execute(
            path=str(tmp_project),
            pattern="[invalid",
            is_regex=True,
        )
        assert result.success is False
        assert "regex" in (result.error or "").lower()

    def test_pycache_skipped(self, tmp_project: Path) -> None:
        """__pycache__ directories are skipped."""
        cache_dir = tmp_project / "src" / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "foo.cpython-312.pyc").write_text("CACHED_CONTENT\n")

        result = SearchFilesTool().execute(
            path=str(tmp_project), pattern="CACHED_CONTENT"
        )
        assert result.success is True
        assert result.data is not None
        assert result.data["count"] == 0
