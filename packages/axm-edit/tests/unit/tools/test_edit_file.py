"""Unit tests for axm_edit.tools.edit_file — EditFileTool (no real I/O)."""

from __future__ import annotations

import pytest

from axm_edit.tools.edit_file import EditFileTool, render_text


class TestRenderText:
    """Tests for the ``render_text`` compact rendering helper."""

    @pytest.mark.parametrize(
        ("replacements", "first_line", "expected"),
        [
            pytest.param(
                1,
                2,
                "edit_file | ✓ | /tmp/f.txt · 1 replacement @ L2",
                id="single_replacement",
            ),
            pytest.param(
                3,
                1,
                "edit_file | ✓ | /tmp/f.txt · 3 replacements @ L1",
                id="many_replacements_pluralised",
            ),
        ],
    )
    def test_render_text_pluralisation(
        self, replacements: int, first_line: int, expected: str
    ) -> None:
        text = render_text(
            path="/tmp/f.txt", replacements=replacements, first_line=first_line
        )
        assert text == expected


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
