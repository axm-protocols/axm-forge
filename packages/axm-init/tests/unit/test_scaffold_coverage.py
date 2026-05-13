"""Unit coverage tests for tools.scaffold — no I/O."""

from __future__ import annotations


class TestScaffoldNameProperty:
    """Cover line 31: name property."""

    def test_name_returns_init_scaffold(self) -> None:
        from axm_init.tools.scaffold import InitScaffoldTool

        tool = InitScaffoldTool()
        assert tool.name == "init_scaffold"


class TestScaffoldValidation:
    """Cover _validate_inputs error path."""

    def test_missing_org_returns_error(self) -> None:
        """Missing org → ToolResult(success=False)."""
        from axm_init.tools.scaffold import InitScaffoldTool

        tool = InitScaffoldTool()
        result = tool.execute(author="Author", email="a@b.com")
        assert result.success is False
        assert "org" in (result.error or "").lower()

    def test_missing_author_returns_error(self) -> None:
        """Missing author → ToolResult(success=False)."""
        from axm_init.tools.scaffold import InitScaffoldTool

        tool = InitScaffoldTool()
        result = tool.execute(org="myorg", email="a@b.com")
        assert result.success is False
        assert "author" in (result.error or "").lower()

    def test_missing_email_returns_error(self) -> None:
        """Missing email → ToolResult(success=False)."""
        from axm_init.tools.scaffold import InitScaffoldTool

        tool = InitScaffoldTool()
        result = tool.execute(org="myorg", author="Author")
        assert result.success is False
        assert "email" in (result.error or "").lower()
