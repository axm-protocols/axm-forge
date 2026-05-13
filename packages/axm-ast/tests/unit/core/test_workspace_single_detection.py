from __future__ import annotations

from axm_ast.tools.callers import CallersTool


def test_invalid_path_returns_error() -> None:
    """Path that does not exist returns ToolResult(success=False)."""
    tool = CallersTool()
    result = tool.execute(path="/nonexistent/path/xyz", symbol="Foo")

    assert result.success is False
    assert "Not a directory" in (result.error or "")
