"""Tests for axm_edit.utils — is_binary detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.utils import is_binary


class TestIsBinaryUnit:
    """Unit tests for is_binary() across byte-content scenarios."""

    @pytest.mark.parametrize(
        ("content", "expected"),
        [
            pytest.param(b"hello\x00world", True, id="null_bytes"),
            pytest.param(
                bytes(range(0x01, 0x20)) * 100, True, id="high_nonprintable_ratio"
            ),
            pytest.param(b"Hello, world!\nLine 2\n", False, id="text_ascii"),
            pytest.param("Héllo café naïve".encode(), False, id="text_utf8_accents"),
            pytest.param(b"", False, id="empty_file"),
            pytest.param(None, False, id="nonexistent_file"),
            pytest.param(
                b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 10, True, id="png_header"
            ),
            pytest.param(
                b"A" * 70 + bytes([0x01]) * 30,
                False,
                id="exactly_30_percent_nonprintable",
            ),
            pytest.param(
                b"col1\tcol2\tcol3\n" * 100, False, id="text_with_tabs_newlines"
            ),
            pytest.param(b"A\x01B", True, id="very_short_file_with_nonprintable"),
        ],
    )
    def test_is_binary(
        self, tmp_path: Path, content: bytes | None, expected: bool
    ) -> None:
        f = tmp_path / "sample"
        if content is not None:
            f.write_bytes(content)
        assert is_binary(f) is expected


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
