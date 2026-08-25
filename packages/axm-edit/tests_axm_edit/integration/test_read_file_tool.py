"""Tests for axm_edit.tools.read_file — ReadFileTool."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from axm_edit.tools.read_file import ReadFileTool


class TestReadFileTool:
    """Tests for the ReadFileTool AXMTool wrapper."""

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

    def test_text_full_file_header_and_no_loss(self, tmp_project: Path) -> None:
        """text carries a 'N lines' header plus the verbatim numbered content."""
        result = ReadFileTool().execute(path=str(tmp_project), file="src/foo.py")
        assert result.success is True
        assert result.data is not None
        assert result.text is not None
        # Header: path + full-file marker (not a partial range)
        assert result.text.startswith("src/foo.py (5 lines)\n")
        # No content loss: the verbatim numbered content is embedded as-is
        assert result.data["content"] in result.text
        assert "   1: import os" in result.text
        assert "   5:     return 42" in result.text

    def test_text_range_header(self, tmp_project: Path) -> None:
        """A partial read renders an 'L{start}-{end} of {total}' header."""
        result = ReadFileTool().execute(
            path=str(tmp_project),
            file="src/foo.py",
            start_line=2,
            end_line=4,
        )
        assert result.success is True
        assert result.text is not None
        assert result.text.startswith("src/foo.py (L2-4 of 5)\n")
        assert "import os" not in result.text

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

    @pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses file permission bits")
    def test_unreadable_file_returns_error_not_raise(self, tmp_project: Path) -> None:
        """An OSError on read is turned into a failed ToolResult, not a leak."""
        unreadable = tmp_project / "src" / "secret.py"
        unreadable.write_text("x = 1\n", encoding="utf-8")
        unreadable.chmod(0o000)
        try:
            result = ReadFileTool().execute(path=str(tmp_project), file="src/secret.py")
        finally:
            unreadable.chmod(0o644)
        assert result.success is False
        assert "read failed" in (result.error or "").lower()


class TestReadFileSkipsBinary:
    """Functional test: ReadFileTool rejects binary files."""

    def test_read_file_skips_binary_nonprintable(self, tmp_project: Path) -> None:
        from axm_edit.tools.read_file import ReadFileTool

        # Create a binary file with high non-printable ratio
        binary_file = tmp_project / "src" / "data.bin"
        binary_file.write_bytes(bytes(range(0x01, 0x20)) * 100)

        result = ReadFileTool().execute(path=str(tmp_project), file="src/data.bin")
        assert result.success is False
        assert "Binary file" in (result.error or "")


class TestReadFileCap:
    """Regression (P1-3): unbounded reads are capped to protect the transport.

    Asserts through the public contract (``truncated`` flag, the ``showing``
    count, the truncation marker in ``content``) rather than the private
    ``_DEFAULT_MAX_LINES`` constant, so the cap is verified by observable
    behaviour. ``_BIG`` is comfortably above any reasonable default cap.
    """

    _BIG = 5000

    def test_large_file_capped(self, tmp_project: Path) -> None:
        from axm_edit.tools.read_file import ReadFileTool

        big = tmp_project / "src" / "big.txt"
        big.write_text("".join(f"line {i}\n" for i in range(self._BIG)))

        result = ReadFileTool().execute(path=str(tmp_project), file="src/big.txt")
        assert result.success is True
        assert result.data is not None
        assert result.data["truncated"] is True
        assert result.data["total_lines"] == self._BIG
        # The cap returns strictly fewer lines than the file holds.
        assert result.data["showing"]["count"] < self._BIG
        assert "truncated" in result.data["content"]

    def test_explicit_range_not_capped(self, tmp_project: Path) -> None:
        from axm_edit.tools.read_file import ReadFileTool

        big = tmp_project / "src" / "big.txt"
        big.write_text("".join(f"line {i}\n" for i in range(self._BIG)))

        # An explicit full-file range bypasses the default cap entirely.
        result = ReadFileTool().execute(
            path=str(tmp_project),
            file="src/big.txt",
            start_line=1,
            end_line=self._BIG,
        )
        assert result.success is True
        assert result.data is not None
        assert result.data["truncated"] is False
        assert result.data["showing"]["count"] == self._BIG
