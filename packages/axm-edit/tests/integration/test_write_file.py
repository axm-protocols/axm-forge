"""Integration tests for axm_edit.tools.write_file — WriteFileTool (real filesystem)."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.tools.write_file import WriteFileTool


class TestWriteFileTool:
    """Tests for WriteFileTool."""

    @pytest.fixture()
    def tool(self) -> WriteFileTool:
        return WriteFileTool()

    @pytest.mark.parametrize(
        ("filename", "content", "expected_bytes"),
        [
            pytest.param("output.md", "# Hello\n", 8, id="new_file"),
            pytest.param("empty.txt", "", 0, id="empty_content"),
        ],
    )
    def test_write_content(
        self,
        tool: WriteFileTool,
        tmp_path: Path,
        filename: str,
        content: str,
        expected_bytes: int,
    ) -> None:
        target = tmp_path / filename
        result = tool.execute(path=str(target), content=content)
        assert result.success is True
        assert result.data["bytes"] == expected_bytes
        assert target.read_text() == content

    def test_creates_parent_dirs(self, tool: WriteFileTool, tmp_path: Path) -> None:
        target = tmp_path / "deep" / "nested" / "file.txt"
        result = tool.execute(path=str(target), content="ok")
        assert result.success is True
        assert target.read_text() == "ok"

    def test_overwrites_existing(self, tool: WriteFileTool, tmp_path: Path) -> None:
        target = tmp_path / "existing.txt"
        target.write_text("old content")
        result = tool.execute(path=str(target), content="new content")
        assert result.success is True
        assert target.read_text() == "new content"

    def test_missing_content(self, tool: WriteFileTool, tmp_path: Path) -> None:
        result = tool.execute(path=str(tmp_path / "f.txt"))
        assert result.success is False
        assert result.error is not None and "content" in result.error

    def test_utf8_content(self, tool: WriteFileTool, tmp_path: Path) -> None:
        target = tmp_path / "unicode.txt"
        text = "Héllo wörld 🌍"
        result = tool.execute(path=str(target), content=text)
        assert result.success is True
        assert target.read_text(encoding="utf-8") == text
