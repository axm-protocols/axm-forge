"""Tests for axm_edit.tools.edit_file — EditFileTool."""

from __future__ import annotations

from pathlib import Path

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

    def test_simple_replace(self, tool: EditFileTool, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text("def foo():\n    return 42\n")
        result = tool.execute(path=str(target), old="return 42", new="return 99")
        assert result.success is True
        assert result.data["replacements"] == 1
        assert result.data["first_line"] == 2
        assert "return 99" in target.read_text()

    def test_text_not_found(self, tool: EditFileTool, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text("def foo():\n    pass\n")
        result = tool.execute(path=str(target), old="nonexistent", new="x")
        assert result.success is False
        assert result.error is not None and "not found" in result.error

    def test_ambiguous_multiple(self, tool: EditFileTool, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text("a = 1\nb = 1\nc = 1\n")
        result = tool.execute(path=str(target), old="= 1", new="= 2")
        assert result.success is False
        assert result.error is not None and "3 occurrences" in result.error

    def test_replace_all_with_count(self, tool: EditFileTool, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text("a = 1\nb = 1\n")
        result = tool.execute(path=str(target), old="= 1", new="= 2", count=-1)
        assert result.success is True
        assert result.data["replacements"] == 2
        assert target.read_text() == "a = 2\nb = 2\n"

    def test_replace_specific_count(self, tool: EditFileTool, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text("a = 1\nb = 1\nc = 1\n")
        result = tool.execute(path=str(target), old="= 1", new="= 2", count=2)
        assert result.success is True
        assert result.data["replacements"] == 2
        assert target.read_text() == "a = 2\nb = 2\nc = 1\n"

    def test_file_not_found(self, tool: EditFileTool, tmp_path: Path) -> None:
        result = tool.execute(path=str(tmp_path / "nope.py"), old="a", new="b")
        assert result.success is False
        assert result.error is not None and "not found" in result.error

    def test_missing_path(self, tool: EditFileTool) -> None:
        result = tool.execute(old="a", new="b")
        assert result.success is False
        assert result.error is not None and "path" in result.error

    def test_missing_old(self, tool: EditFileTool, tmp_path: Path) -> None:
        result = tool.execute(path=str(tmp_path / "f.py"), new="b")
        assert result.success is False
        assert result.error is not None and "old" in result.error

    def test_missing_new(self, tool: EditFileTool, tmp_path: Path) -> None:
        result = tool.execute(path=str(tmp_path / "f.py"), old="a")
        assert result.success is False
        assert result.error is not None and "new" in result.error

    def test_multiline_replace(self, tool: EditFileTool, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text("def foo():\n    pass\n\ndef bar():\n    pass\n")
        result = tool.execute(
            path=str(target),
            old="def foo():\n    pass",
            new="def foo():\n    return 1",
        )
        assert result.success is True
        assert "return 1" in target.read_text()
        assert result.data["first_line"] == 1
