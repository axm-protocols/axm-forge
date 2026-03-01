"""Tests for tools.reserve — test mirror."""

from __future__ import annotations


class TestReserveToolImport:
    """Smoke: reserve tool is importable."""

    def test_import_init_reserve_tool(self) -> None:
        """InitReserveTool is importable."""
        from axm_init.tools.reserve import InitReserveTool

        assert InitReserveTool is not None


class TestReserveToolValidation:
    """Validate required kwargs handling."""

    def test_missing_name_returns_error(self) -> None:
        """Calling execute() without 'name' returns a ToolResult error."""
        from axm_init.tools.reserve import InitReserveTool

        tool = InitReserveTool()
        result = tool.execute()
        assert result.success is False
        assert "'name' is required" in (result.error or "")
