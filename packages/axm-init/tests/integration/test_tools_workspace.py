"""Tests for MCP tool workspace support (AXM-307).

Tests that:
- InitCheckTool returns context/workspace_root/excluded_checks in ToolResult.data
- InitScaffoldTool accepts workspace=True and routes to workspace template
- InitScaffoldTool accepts member="name" and routes to member template + patcher
- InitScaffoldTool defaults to standalone template when neither flag is set
- format_agent includes all context fields in output
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from axm_init.models.check import CheckResult, ProjectResult
from axm_init.tools.scaffold import InitScaffoldTool


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


class TestScaffoldToolMemberMode:
    """AC3: InitScaffoldTool accepts member kwarg."""

    def test_scaffold_tool_member_mode(
        self,
        scaffold_tool: InitScaffoldTool,
        tmp_path: Path,
        base_kwargs: dict[str, Any],
    ) -> None:
        # Create a workspace structure
        ws_root = tmp_path
        pyproject = ws_root / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "test-ws"\n\n'
            "[tool.uv.workspace]\n"
            'members = ["packages/*"]\n'
        )
        (ws_root / "Makefile").write_text("test-all:\n\techo test\n")
        (ws_root / "mkdocs.yml").write_text(
            "site_name: test\nnav:\n  - Home: index.md\n"
        )
        ci_dir = ws_root / ".github" / "workflows"
        ci_dir.mkdir(parents=True)
        (ci_dir / "ci.yml").write_text(
            "jobs:\n  test:\n    strategy:\n      matrix:\n"
            "        package:\n          - existing\n"
            "    steps:\n      - run: echo test\n"
        )
        publish_content = (
            "name: Publish\non:\n  push:\n"
            '    tags:\n      - "v*"\n'
            "jobs:\n  pub:\n    runs-on: ubuntu-latest\n"
        )
        (ci_dir / "publish.yml").write_text(publish_content)

        base_kwargs["path"] = str(ws_root)
        base_kwargs["member"] = "my-lib"

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.files_created = [Path("pyproject.toml")]

        with patch("axm_init.adapters.copier.CopierAdapter") as mock_copier_cls:
            mock_copier = MagicMock()
            mock_copier.copy.return_value = mock_result
            mock_copier_cls.return_value = mock_copier

            tool_result = scaffold_tool.execute(**base_kwargs)

        assert tool_result.success is True
        assert tool_result.data is not None
        assert tool_result.data["member"] == "my-lib"
        assert "patched_root_files" in tool_result.data

    def test_scaffold_member_not_in_workspace(
        self,
        scaffold_tool: InitScaffoldTool,
        tmp_path: Path,
        base_kwargs: dict[str, Any],
    ) -> None:
        """Member scaffold fails outside workspace."""
        base_kwargs["path"] = str(tmp_path)
        base_kwargs["member"] = "my-lib"

        tool_result = scaffold_tool.execute(**base_kwargs)

        assert tool_result.success is False
        assert "workspace" in (tool_result.error or "").lower()


class TestFormatAgentIncludesContext:
    """AC5: format_agent includes context, workspace_root, excluded_checks."""

    def test_format_agent_all_context_fields(self, tmp_path: Path) -> None:
        from axm_init.core.checker import format_agent

        result = _make_project_result(
            tmp_path,
            context="member",
            workspace_root=tmp_path.parent,
            excluded_checks=["ci.ci_workflow_exists", "tooling.makefile"],
        )

        output = format_agent(result)

        assert output["context"] == "member"
        assert output["workspace_root"] == str(tmp_path.parent)
        assert output["excluded_checks"] == [
            "ci.ci_workflow_exists",
            "tooling.makefile",
        ]
        assert "score" in output
        assert "grade" in output
        assert "passed_count" in output
        assert "failed" in output
