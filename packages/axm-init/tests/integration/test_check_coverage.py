"""Coverage tests for tools.check — error and success paths in execute."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


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


class TestCheckExecuteSuccessPath:
    """Cover happy path through execute."""

    def test_execute_success_with_category(self, tmp_path: Path) -> None:
        """Successful run with category filter returns formatted data."""
        from axm_init.tools.check import InitCheckTool

        mock_engine_cls = MagicMock()
        mock_engine_cls.return_value.run.return_value = "raw-result"

        tool = InitCheckTool()
        with (
            patch("axm_init.core.checker.CheckEngine", mock_engine_cls),
            patch(
                "axm_init.core.checker.format_agent",
                return_value={"score": 95},
            ) as mock_fmt,
        ):
            result = tool.execute(path=str(tmp_path), category="lint")

        assert result.success is True
        assert result.data == {"score": 95}
        mock_engine_cls.assert_called_once_with(tmp_path.resolve(), category="lint")
        mock_fmt.assert_called_once_with("raw-result")

    def test_execute_default_path(self) -> None:
        """Default path='.' is resolved."""
        from axm_init.tools.check import InitCheckTool

        mock_engine_cls = MagicMock()
        mock_engine_cls.return_value.run.return_value = "r"

        tool = InitCheckTool()
        with (
            patch("axm_init.core.checker.CheckEngine", mock_engine_cls),
            patch("axm_init.core.checker.format_agent", return_value={}),
        ):
            result = tool.execute()

        assert result.success is True
        mock_engine_cls.assert_called_once_with(Path(".").resolve(), category=None)
