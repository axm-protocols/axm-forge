"""Unit tests for axm_edit.tools.write_file — WriteFileTool (no real I/O)."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.tools.write_file import WriteFileTool, render_text


class TestRenderText:
    """Tests for the ``render_text`` compact rendering helper."""

    def test_header_carries_path_and_bytes(self) -> None:
        text = render_text(path="/tmp/out.txt", byte_count=18)
        assert text == "write_file | ✓ | /tmp/out.txt · 18 bytes"

    def test_singular_byte(self) -> None:
        text = render_text(path="/tmp/x", byte_count=1)
        assert text.endswith("· 1 byte")


class TestWriteFileTool:
    """Tests for WriteFileTool."""

    @pytest.fixture()
    def tool(self) -> WriteFileTool:
        return WriteFileTool()

    def test_name(self, tool: WriteFileTool) -> None:
        assert tool.name == "write_file"

    def test_agent_hint_exists(self, tool: WriteFileTool) -> None:
        assert tool.agent_hint

    def test_missing_file(self, tool: WriteFileTool) -> None:
        result = tool.execute(content="hello")
        assert result.success is False
        assert result.error is not None and "file" in result.error

    def test_escape_outside_root_refused(
        self, tool: WriteFileTool, tmp_path: Path
    ) -> None:
        """AC1: an absolute target outside root is refused on confinement."""
        outside = tmp_path.parent / "escapee.txt"
        result = tool.execute(path=str(tmp_path), file=str(outside), content="x")
        assert result.success is False
        assert result.error is not None and "confinement" in result.error
        assert not outside.exists()

    def test_in_root_relative_write_succeeds(
        self, tool: WriteFileTool, tmp_path: Path
    ) -> None:
        """AC3: a legitimate in-root relative write still succeeds."""
        result = tool.execute(path=str(tmp_path), file="sub/out.txt", content="hi")
        assert result.success is True
        assert (tmp_path / "sub" / "out.txt").read_text() == "hi"
