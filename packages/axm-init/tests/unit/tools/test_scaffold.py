"""Tests for tools.scaffold — test mirror."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from axm_init.tools.scaffold import InitScaffoldTool

# --- merged from test_scaffold_coverage.py ---


class TestScaffoldNameProperty:
    """Cover line 31: name property."""

    def test_name_returns_init_scaffold(self) -> None:
        tool = InitScaffoldTool()
        assert tool.name == "init_scaffold"


class TestScaffoldValidation:
    """Cover _validate_inputs error path."""

    def test_missing_org_returns_error(self) -> None:
        """Missing org → ToolResult(success=False)."""
        tool = InitScaffoldTool()
        result = tool.execute(author="Author", email="a@b.com")
        assert result.success is False
        assert "org" in (result.error or "").lower()

    def test_missing_author_returns_error(self) -> None:
        """Missing author → ToolResult(success=False)."""
        tool = InitScaffoldTool()
        result = tool.execute(org="myorg", email="a@b.com")
        assert result.success is False
        assert "author" in (result.error or "").lower()

    def test_missing_email_returns_error(self) -> None:
        """Missing email → ToolResult(success=False)."""
        tool = InitScaffoldTool()
        result = tool.execute(org="myorg", author="Author")
        assert result.success is False
        assert "email" in (result.error or "").lower()


# --- merged from test_scaffold_validate.py ---


class TestExtractedValidateInputs:
    """Tests for the extracted input validation helper."""

    def test_missing_org_returns_error(self) -> None:
        tool = InitScaffoldTool()
        result = tool.execute(path=".", author="a", email="e@x.com", org="")
        assert not result.success
        assert result.error is not None
        assert "org" in result.error.lower() or "required" in result.error.lower()

    def test_missing_author_returns_error(self) -> None:
        tool = InitScaffoldTool()
        result = tool.execute(path=".", author="", email="e@x.com", org="myorg")
        assert not result.success
        assert result.error is not None
        assert "required" in result.error.lower()

    def test_missing_email_returns_error(self) -> None:
        tool = InitScaffoldTool()
        result = tool.execute(path=".", author="a", email="", org="myorg")
        assert not result.success
        assert result.error is not None
        assert "required" in result.error.lower()

    def test_valid_inputs_no_validation_error(
        self, tmp_path: Path, mocker: Any
    ) -> None:
        """Valid inputs should pass validation and reach scaffold logic."""
        mock_copy = mocker.patch(
            "axm_init.adapters.copier.CopierAdapter.copy",
        )
        mock_copy.return_value = mocker.MagicMock(
            success=True,
            files_created=[],
            message="",
        )
        mocker.patch(
            "axm_init.core.templates.get_template_path",
            return_value=str(tmp_path),
        )
        tool = InitScaffoldTool()
        result = tool.execute(
            path=str(tmp_path),
            author="Author",
            email="a@b.com",
            org="myorg",
        )
        if not result.success:
            assert result.error is not None
            assert "required" not in result.error.lower()


# --- merged from test_tools_workspace.py (InitScaffoldTool) ---


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


class TestScaffoldToolTemplateSelection:
    """InitScaffoldTool.execute() selects template based on workspace flag."""

    @pytest.mark.parametrize(
        ("workspace_flag", "expected_template_name", "expected_template_type"),
        [
            pytest.param(True, "workspace", "WORKSPACE", id="workspace_mode"),
            pytest.param(None, "standalone", "STANDALONE", id="default_standalone"),
        ],
    )
    def test_scaffold_tool_template_selection(  # noqa: PLR0913
        self,
        scaffold_tool: InitScaffoldTool,
        tmp_path: Path,
        base_kwargs: dict[str, Any],
        workspace_flag: bool | None,
        expected_template_name: str,
        expected_template_type: str,
    ) -> None:
        base_kwargs["path"] = str(tmp_path)
        if workspace_flag is not None:
            base_kwargs["workspace"] = workspace_flag

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
        assert tool_result.data["template"] == expected_template_name

        from axm_init.core.templates import TemplateType

        mock_get_path.assert_called_once_with(
            getattr(TemplateType, expected_template_type)
        )
