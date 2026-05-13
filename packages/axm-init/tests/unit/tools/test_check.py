"""Tests for tools.check — test mirror."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from axm_init.models.check import CheckResult, ProjectResult
from axm_init.tools.check import InitCheckTool


class TestCheckTool:
    """Contract checks for InitCheckTool."""

    def test_has_name_property(self) -> None:
        """InitCheckTool.name returns 'init_check'."""
        tool = InitCheckTool()
        assert tool.name == "init_check"

    def test_has_execute_method(self) -> None:
        """InitCheckTool has an execute method (Protocol compliance)."""
        tool = InitCheckTool()
        assert callable(tool.execute)


# --- merged from test_check_coverage.py ---


class TestCheckExecuteSuccessPath:
    """Cover happy path through execute."""

    def test_execute_success_with_category(self, tmp_path: Path) -> None:
        """Successful run with category filter returns formatted data."""
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


# --- merged from test_tools_workspace.py (InitCheckTool) ---


@pytest.fixture()
def check_tool() -> InitCheckTool:
    return InitCheckTool()


def _make_project_result(
    tmp_path: Path,
    *,
    context: str = "workspace",
    workspace_root: Path | None = None,
    excluded_checks: list[str] | None = None,
) -> ProjectResult:
    """Build a minimal ProjectResult with context info."""
    check = CheckResult(
        name="test.dummy",
        category="test",
        passed=True,
        weight=10,
        message="OK",
        details=[],
        fix="",
    )
    return ProjectResult.from_checks(
        tmp_path,
        [check],
        context=context,
        workspace_root=workspace_root or tmp_path,
        excluded_checks=excluded_checks or ["ci.ci_workflow_exists"],
    )


class TestCheckToolReturnsContext:
    """AC1: InitCheckTool.execute() returns context info in ToolResult.data."""

    def test_check_tool_returns_context(
        self, check_tool: InitCheckTool, tmp_path: Path
    ) -> None:
        result = _make_project_result(tmp_path, context="workspace")

        with (
            patch("axm_init.core.checker.CheckEngine") as mock_engine_cls,
            patch("axm_init.core.checker.format_agent", wraps=None) as mock_format,
        ):
            mock_engine = MagicMock()
            mock_engine.run.return_value = result
            mock_engine_cls.return_value = mock_engine
            mock_format.return_value = {
                "score": 100,
                "grade": "A",
                "context": "workspace",
                "workspace_root": str(tmp_path),
                "excluded_checks": ["ci.ci_workflow_exists"],
                "passed_count": 1,
                "failed": [],
            }

            tool_result = check_tool.execute(path=str(tmp_path))

        assert tool_result.success is True
        assert tool_result.data is not None
        assert tool_result.data["context"] == "workspace"
        assert tool_result.data["workspace_root"] == str(tmp_path)
        assert "excluded_checks" in tool_result.data


# Silence unused-import warning for Any (kept for parity with original).
_ = Any
