"""Tests for tools.check — test mirror."""

from __future__ import annotations


class TestCheckTool:
    """Contract checks for InitCheckTool."""

    def test_has_name_property(self) -> None:
        """InitCheckTool.name returns 'init_check'."""
        from axm_init.tools.check import InitCheckTool

        tool = InitCheckTool()
        assert tool.name == "init_check"

    def test_has_execute_method(self) -> None:
        """InitCheckTool has an execute method (Protocol compliance)."""
        from axm_init.tools.check import InitCheckTool

        tool = InitCheckTool()
        assert callable(tool.execute)
