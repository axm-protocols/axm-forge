"""Unit tests for axm_edit.tools.write_file — WriteFileTool (no real I/O)."""

from __future__ import annotations

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

    def test_missing_path(self, tool: WriteFileTool) -> None:
        result = tool.execute(content="hello")
        assert result.success is False
        assert result.error is not None and "path" in result.error
