"""Coverage tests for tools.check — error and success paths in execute."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


class TestCheckExecuteErrorPath:
    """Cover lines 40, 49-50: not-a-directory and exception handling."""

    def test_nonexistent_path_returns_error(self, tmp_path: Path) -> None:
        """Path that does not exist → ToolResult(success=False)."""
        from axm_init.tools.check import InitCheckTool

        tool = InitCheckTool()
        fake = tmp_path / "does-not-exist"
        result = tool.execute(path=str(fake))
        assert result.success is False
        assert "Not a directory" in (result.error or "")

    def test_file_path_returns_error(self, tmp_path: Path) -> None:
        """Path pointing to a file (not dir) → ToolResult(success=False)."""
        from axm_init.tools.check import InitCheckTool

        f = tmp_path / "file.txt"
        f.write_text("content")
        tool = InitCheckTool()
        result = tool.execute(path=str(f))
        assert result.success is False
        assert "Not a directory" in (result.error or "")

    def test_check_engine_exception_caught(self, tmp_path: Path) -> None:
        """Exception from CheckEngine → ToolResult(success=False)."""
        from axm_init.tools.check import InitCheckTool

        tool = InitCheckTool()
        with patch(
            "axm_init.core.checker.CheckEngine",
            side_effect=RuntimeError("engine failure"),
        ):
            result = tool.execute(path=str(tmp_path))
        assert result.success is False
        assert "engine failure" in (result.error or "")
