"""Unit tests for MCP tool workspace support (AXM-307)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from axm_init.models.check import CheckResult, ProjectResult
from axm_init.tools.check import InitCheckTool
from axm_init.tools.scaffold import InitScaffoldTool


@pytest.fixture()
def check_tool() -> InitCheckTool:
    return InitCheckTool()


@pytest.fixture()
def scaffold_tool() -> InitScaffoldTool:
    return InitScaffoldTool()


@pytest.fixture()
def base_kwargs() -> dict[str, Any]:
    """Minimal kwargs required by scaffold tool."""
    return {
        "org": "test-org",
        "author": "Test Author",
        "email": "test@example.com",
    }


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


class TestScaffoldToolWorkspaceMode:
    """AC2: InitScaffoldTool.execute() accepts workspace=True → workspace template."""

    def test_scaffold_tool_workspace_mode(
        self,
        scaffold_tool: InitScaffoldTool,
        tmp_path: Path,
        base_kwargs: dict[str, Any],
    ) -> None:
        base_kwargs["path"] = str(tmp_path)
        base_kwargs["workspace"] = True

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.files_created = [tmp_path / "pyproject.toml"]

        with (
            patch("axm_init.adapters.copier.CopierAdapter") as mock_copier_cls,
            patch("axm_init.core.templates.get_template_path") as mock_get_path,
        ):
            mock_copier = MagicMock()
            mock_copier.copy.return_value = mock_result
            mock_copier_cls.return_value = mock_copier
            mock_get_path.return_value = Path("/fake/template")

            tool_result = scaffold_tool.execute(**base_kwargs)

        assert tool_result.success is True
        assert tool_result.data is not None
        assert tool_result.data["template"] == "workspace"

        # Verify workspace template type was requested
        from axm_init.core.templates import TemplateType

        mock_get_path.assert_called_once_with(TemplateType.WORKSPACE)


class TestScaffoldToolDefaultStandalone:
    """AC4: Default scaffold (no workspace/member) uses standalone template."""

    def test_scaffold_tool_default_standalone(
        self,
        scaffold_tool: InitScaffoldTool,
        tmp_path: Path,
        base_kwargs: dict[str, Any],
    ) -> None:
        base_kwargs["path"] = str(tmp_path)

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.files_created = [tmp_path / "pyproject.toml"]

        with (
            patch("axm_init.adapters.copier.CopierAdapter") as mock_copier_cls,
            patch("axm_init.core.templates.get_template_path") as mock_get_path,
        ):
            mock_copier = MagicMock()
            mock_copier.copy.return_value = mock_result
            mock_copier_cls.return_value = mock_copier
            mock_get_path.return_value = Path("/fake/template")

            tool_result = scaffold_tool.execute(**base_kwargs)

        assert tool_result.success is True
        assert tool_result.data is not None
        assert tool_result.data["template"] == "standalone"

        from axm_init.core.templates import TemplateType

        mock_get_path.assert_called_once_with(TemplateType.STANDALONE)
