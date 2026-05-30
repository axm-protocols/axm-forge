"""Tests for axm_edit.tools.run_command — RunCommandTool."""

from __future__ import annotations

from axm_edit.tools.run_command import RunCommandTool


class TestRunCommandTool:
    """Tests for the RunCommandTool AXMTool wrapper."""

    def test_name(self) -> None:
        tool = RunCommandTool()
        assert tool.name == "run_command"

    def test_bad_root(self) -> None:
        """Non-existent root directory returns error."""
        result = RunCommandTool().execute(path="/nonexistent/root", command="echo test")
        assert result.success is False
        assert "not a directory" in (result.error or "").lower()
