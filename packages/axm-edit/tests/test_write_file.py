"""Tests for axm_edit.tools.write_file — WriteFileTool."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.tools.write_file import WriteFileTool


class TestWriteFileTool:
    """Tests for WriteFileTool."""

    @pytest.fixture()
    def tool(self) -> WriteFileTool:
        return WriteFileTool()

    def test_name(self, tool: WriteFileTool) -> None:
        assert tool.name == "write_file"

    def test_agent_hint_exists(self, tool: WriteFileTool) -> None:
        assert tool.agent_hint

    def test_write_new_file(self, tool: WriteFileTool, tmp_path: Path) -> None:
        target = tmp_path / "output.md"
        result = tool.execute(path=str(target), content="# Hello\n")
        assert result.success is True
        assert result.data["bytes"] == 8
        assert target.read_text() == "# Hello\n"

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

    def test_empty_content(self, tool: WriteFileTool, tmp_path: Path) -> None:
        target = tmp_path / "empty.txt"
        result = tool.execute(path=str(target), content="")
        assert result.success is True
        assert target.read_text() == ""
        assert result.data["bytes"] == 0

    def test_missing_path(self, tool: WriteFileTool) -> None:
        result = tool.execute(content="hello")
        assert result.success is False
        assert result.error is not None and "path" in result.error

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
