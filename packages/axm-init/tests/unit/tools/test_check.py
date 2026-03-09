"""Tests for tools.check — test mirror."""

from __future__ import annotations


class TestCheckToolImport:
    """Smoke: check tool is importable."""

    def test_import_init_check_tool(self) -> None:
        """InitCheckTool is importable."""
        from axm_init.tools.check import InitCheckTool

        assert InitCheckTool is not None

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
