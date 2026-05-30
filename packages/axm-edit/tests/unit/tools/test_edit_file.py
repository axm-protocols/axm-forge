"""Unit tests for axm_edit.tools.edit_file — EditFileTool (no real I/O)."""

from __future__ import annotations

import pytest

from axm_edit.tools.edit_file import EditFileTool


class TestEditFileTool:
    """Tests for EditFileTool."""

    @pytest.fixture()
    def tool(self) -> EditFileTool:
        return EditFileTool()

    def test_name(self, tool: EditFileTool) -> None:
        assert tool.name == "edit_file"

    def test_agent_hint_exists(self, tool: EditFileTool) -> None:
        assert tool.agent_hint

    def test_missing_path(self, tool: EditFileTool) -> None:
        result = tool.execute(old="a", new="b")
        assert result.success is False
        assert result.error is not None and "path" in result.error
