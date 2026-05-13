"""Unit coverage tests for tools.check — success path through execute."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


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
