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

    def test_tool_rejects_empty_author(self) -> None:
        """Empty author returns error."""
        from axm_init.tools.reserve import InitReserveTool

        tool = InitReserveTool()
        result = tool.execute(name="test-pkg", author="", email="a@b.com")
        assert result.success is False
        assert "author" in (result.error or "").lower()

    def test_tool_rejects_placeholder_author(self) -> None:
        """Placeholder 'John Doe' author returns error."""
        from axm_init.tools.reserve import InitReserveTool

        tool = InitReserveTool()
        result = tool.execute(
            name="test-pkg", author="John Doe", email="real@email.com"
        )
        assert result.success is False
        assert "placeholder" in (result.error or "").lower()

    def test_tool_rejects_empty_email(self) -> None:
        """Empty email returns error."""
        from axm_init.tools.reserve import InitReserveTool

        tool = InitReserveTool()
        result = tool.execute(name="test-pkg", author="Real Author", email="")
        assert result.success is False
        assert "email" in (result.error or "").lower()

    def test_tool_rejects_placeholder_email(self) -> None:
        """Placeholder email returns error."""
        from axm_init.tools.reserve import InitReserveTool

        tool = InitReserveTool()
        result = tool.execute(
            name="test-pkg",
            author="Real Author",
            email="john.doe@example.com",
        )
        assert result.success is False
        assert "placeholder" in (result.error or "").lower()
