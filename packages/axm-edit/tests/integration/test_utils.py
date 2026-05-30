"""Tests for axm_edit.utils — is_binary detection."""

from __future__ import annotations

from pathlib import Path

from axm_edit.utils import is_binary


class TestIsBinaryUnit:
    """Unit tests for is_binary()."""

    def test_binary_null_bytes(self, tmp_path: Path) -> None:
        f = tmp_path / "nulls.bin"
        f.write_bytes(b"hello\x00world")
        assert is_binary(f) is True

    def test_binary_high_nonprintable_ratio(self, tmp_path: Path) -> None:
        f = tmp_path / "nonprint.bin"
        f.write_bytes(bytes(range(0x01, 0x20)) * 100)
        assert is_binary(f) is True

    def test_text_ascii(self, tmp_path: Path) -> None:
        f = tmp_path / "text.txt"
        f.write_bytes(b"Hello, world!\nLine 2\n")
        assert is_binary(f) is False

    def test_text_utf8_accents(self, tmp_path: Path) -> None:
        f = tmp_path / "accents.txt"
        f.write_bytes("Héllo café naïve".encode())
        assert is_binary(f) is False

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty"
        f.write_bytes(b"")
        assert is_binary(f) is False

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        f = tmp_path / "nope.txt"
        assert is_binary(f) is False

    def test_png_header(self, tmp_path: Path) -> None:
        f = tmp_path / "image.png"
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 10)
        assert is_binary(f) is True


class TestIsBinaryEdgeCases:
    """Edge-case tests for is_binary()."""

    def test_exactly_30_percent_nonprintable(self, tmp_path: Path) -> None:
        """Exactly 30% non-printable → False (threshold is strict >)."""
        # 70 printable + 30 non-printable = 30% exactly
        printable = b"A" * 70
        nonprintable = bytes([0x01]) * 30
        f = tmp_path / "edge30.bin"
        f.write_bytes(printable + nonprintable)
        assert is_binary(f) is False

    def test_text_with_tabs_newlines(self, tmp_path: Path) -> None:
        """Tabs/newlines should not count as non-printable."""
        f = tmp_path / "logs.txt"
        f.write_bytes(b"col1\tcol2\tcol3\n" * 100)
        assert is_binary(f) is False

    def test_very_short_file_with_nonprintable(self, tmp_path: Path) -> None:
        """Short file b'A\\x01B' — ratio 33% → True."""
        f = tmp_path / "short.bin"
        f.write_bytes(b"A\x01B")
        assert is_binary(f) is True


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


class TestSearchFilesSkipsBinary:
    """Functional test: SearchFilesTool skips binary files."""

    def test_search_files_skips_binary_nonprintable(self, tmp_project: Path) -> None:
        from axm_edit.tools.search_files import SearchFilesTool

        # Create a binary file containing the search pattern
        binary_file = tmp_project / "src" / "data.bin"
        binary_file.write_bytes(b"import os" + bytes(range(0x01, 0x20)) * 100)

        # Also ensure a text file has the pattern (already in foo.py)
        result = SearchFilesTool().execute(path=str(tmp_project), pattern="import os")
        assert result.success is True
        assert result.data is not None
        files = [m["file"] for m in result.data["matches"]]
        assert "src/data.bin" not in files
        assert any("foo.py" in f for f in files)
