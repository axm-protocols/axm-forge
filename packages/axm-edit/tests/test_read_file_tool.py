"""Tests for axm_edit.tools.read_file — ReadFileTool."""

from __future__ import annotations

from pathlib import Path

from axm_edit.tools.read_file import ReadFileTool


class TestReadFileTool:
    """Tests for the ReadFileTool AXMTool wrapper."""

    def test_name(self) -> None:
        tool = ReadFileTool()
        assert tool.name == "read_file"

    def test_read_full_file(self, tmp_project: Path) -> None:
        """Reading without line range returns all lines with numbers."""
        result = ReadFileTool().execute(path=str(tmp_project), file="src/foo.py")
        assert result.success is True
        assert result.data is not None
        assert result.data["total_lines"] == 5
        assert result.data["showing"]["count"] == 5
        assert "   1: import os" in result.data["content"]
        assert "   5:     return 42" in result.data["content"]

    def test_read_line_range(self, tmp_project: Path) -> None:
        """Reading with start/end returns only requested range."""
        result = ReadFileTool().execute(
            path=str(tmp_project),
            file="src/foo.py",
            start_line=2,
            end_line=4,
        )
        assert result.success is True
        assert result.data is not None
        assert result.data["showing"]["start"] == 2
        assert result.data["showing"]["end"] == 4
        assert result.data["showing"]["count"] == 3
        assert result.data["total_lines"] == 5
        assert "   2: import sys" in result.data["content"]
        assert "   4: def hello():" in result.data["content"]
        # Line 1 should NOT be in the output
        assert "import os" not in result.data["content"]

    def test_read_returns_total_lines(self, tmp_project: Path) -> None:
        """Metadata always contains total_lines regardless of range."""
        result = ReadFileTool().execute(
            path=str(tmp_project),
            file="src/bar.py",
            start_line=1,
            end_line=2,
        )
        assert result.success is True
        assert result.data is not None
        assert result.data["total_lines"] == 7

    def test_missing_file_argument(self, tmp_project: Path) -> None:
        """Missing 'file' param returns error."""
        result = ReadFileTool().execute(path=str(tmp_project))
        assert result.success is False
        assert "file" in (result.error or "").lower()

    def test_nonexistent_file(self, tmp_project: Path) -> None:
        """Non-existent file returns error."""
        result = ReadFileTool().execute(path=str(tmp_project), file="src/nope.py")
        assert result.success is False
        assert "not found" in (result.error or "").lower()

    def test_binary_file(self, tmp_project: Path) -> None:
        """Binary files are rejected."""
        binary = tmp_project / "image.png"
        binary.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
        result = ReadFileTool().execute(path=str(tmp_project), file="image.png")
        assert result.success is False
        assert "binary" in (result.error or "").lower()

    def test_out_of_range_clamped(self, tmp_project: Path) -> None:
        """Out-of-range lines are clamped, not errored."""
        result = ReadFileTool().execute(
            path=str(tmp_project),
            file="src/foo.py",
            start_line=3,
            end_line=100,
        )
        assert result.success is True
        assert result.data is not None
        # Should return lines 3 to 5 (clamped to file end)
        assert result.data["showing"]["start"] == 3
        assert result.data["showing"]["end"] == 5
        assert result.data["showing"]["count"] == 3

    def test_invalid_range(self, tmp_project: Path) -> None:
        """start_line > end_line returns error."""
        result = ReadFileTool().execute(
            path=str(tmp_project),
            file="src/foo.py",
            start_line=5,
            end_line=2,
        )
        assert result.success is False
        assert "invalid range" in (result.error or "").lower()

    def test_path_traversal(self, tmp_project: Path) -> None:
        """Path traversal is blocked."""
        result = ReadFileTool().execute(path=str(tmp_project), file="../../etc/passwd")
        assert result.success is False
        assert "escapes" in (result.error or "").lower()

    def test_bad_root(self) -> None:
        """Non-existent root directory returns error."""
        result = ReadFileTool().execute(path="/nonexistent/root", file="foo.py")
        assert result.success is False
        assert "not a directory" in (result.error or "").lower()

    def test_start_line_only(self, tmp_project: Path) -> None:
        """start_line without end_line reads to end of file."""
        result = ReadFileTool().execute(
            path=str(tmp_project),
            file="src/foo.py",
            start_line=4,
        )
        assert result.success is True
        assert result.data is not None
        assert result.data["showing"]["start"] == 4
        assert result.data["showing"]["end"] == 5
        assert result.data["showing"]["count"] == 2

    def test_end_line_only(self, tmp_project: Path) -> None:
        """end_line without start_line reads from line 1."""
        result = ReadFileTool().execute(
            path=str(tmp_project),
            file="src/foo.py",
            end_line=3,
        )
        assert result.success is True
        assert result.data is not None
        assert result.data["showing"]["start"] == 1
        assert result.data["showing"]["end"] == 3
        assert result.data["showing"]["count"] == 3
