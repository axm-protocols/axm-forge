"""Tests for tools.check — test mirror."""

from __future__ import annotations

from axm.tools.base import AXMTool


class TestCheckToolImport:
    """Smoke: check tool is importable."""

    def test_import_init_check_tool(self) -> None:
        """InitCheckTool is importable."""
        from axm_init.tools.check import InitCheckTool

        assert InitCheckTool is not None


class TestCheckToolInheritance:
    """Verify AXMTool protocol compliance."""

    def test_inherits_axm_tool(self) -> None:
        """InitCheckTool inherits from AXMTool."""
        from axm_init.tools.check import InitCheckTool

        tool = InitCheckTool()
        assert isinstance(tool, AXMTool)

    def test_has_name_property(self) -> None:
        """InitCheckTool.name returns 'init_check'."""
        from axm_init.tools.check import InitCheckTool

        tool = InitCheckTool()
        assert tool.name == "init_check"
