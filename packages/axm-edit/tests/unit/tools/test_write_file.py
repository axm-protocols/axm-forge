"""Unit tests for axm_edit.tools.write_file — WriteFileTool (no real I/O)."""

from __future__ import annotations

import pytest

from axm_edit.tools.write_file import WriteFileTool, _render_text


class TestRenderText:
    """Tests for the ``_render_text`` compact rendering helper."""

    def test_header_carries_path_and_bytes(self) -> None:
        text = _render_text(path="/tmp/out.txt", byte_count=18)
        assert text == "write_file | ✓ | /tmp/out.txt · 18 bytes"

    def test_singular_byte(self) -> None:
        text = _render_text(path="/tmp/x", byte_count=1)
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

    def test_missing_path(self, tool: WriteFileTool) -> None:
        result = tool.execute(content="hello")
        assert result.success is False
        assert result.error is not None and "path" in result.error
