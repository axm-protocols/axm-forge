"""Unit tests for axm_edit.tools.edit_file — EditFileTool (no real I/O)."""

from __future__ import annotations

import pytest

from axm_edit.tools.edit_file import EditFileTool, _render_text


class TestRenderText:
    """Tests for the ``_render_text`` compact rendering helper."""

    def test_single_replacement(self) -> None:
        text = _render_text(path="/tmp/f.txt", replacements=1, first_line=2)
        assert text == "edit_file | ✓ | /tmp/f.txt · 1 replacement @ L2"

    def test_many_replacements_pluralised(self) -> None:
        text = _render_text(path="/tmp/f.txt", replacements=3, first_line=1)
        assert text == "edit_file | ✓ | /tmp/f.txt · 3 replacements @ L1"


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
