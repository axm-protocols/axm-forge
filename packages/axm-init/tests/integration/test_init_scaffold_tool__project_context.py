"""Coverage tests for tools.scaffold — error paths and edge cases."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


def test_resolve_workspace_root_member_context(tmp_path: Path) -> None:
    """MEMBER context → calls find_workspace_root."""
    from axm_init.tools.scaffold import InitScaffoldTool

    tool = InitScaffoldTool()
    with (
        patch(
            "axm_init.checks._workspace.detect_context",
            return_value="member",
        ),
        patch(
            "axm_init.checks._workspace.find_workspace_root",
            return_value=tmp_path,
        ),
    ):
        # ProjectContext.MEMBER is the string "member"
        from axm_init.checks._workspace import ProjectContext

        with patch(
            "axm_init.checks._workspace.detect_context",
            return_value=ProjectContext.MEMBER,
        ):
            result = tool._resolve_workspace_root(tmp_path / "packages" / "pkg")
    assert result == tmp_path


def test_resolve_workspace_root_standalone(tmp_path: Path) -> None:
    """STANDALONE context → returns None."""
    from axm_init.checks._workspace import ProjectContext
    from axm_init.tools.scaffold import InitScaffoldTool

    tool = InitScaffoldTool()
    with patch(
        "axm_init.checks._workspace.detect_context",
        return_value=ProjectContext.STANDALONE,
    ):
        result = tool._resolve_workspace_root(tmp_path)
    assert result is None


class TestScaffoldMember:
    """Cover lines 231, 255: member scaffold error paths."""

    def test_member_already_exists(self, tmp_path: Path) -> None:
        """Member dir already exists → ToolResult(success=False)."""
        from axm_init.checks._workspace import ProjectContext
        from axm_init.tools.scaffold import InitScaffoldTool

        # Create workspace structure
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        )
        member_dir = tmp_path / "packages" / "existing-pkg"
        member_dir.mkdir(parents=True)

        tool = InitScaffoldTool()
        with patch(
            "axm_init.checks._workspace.detect_context",
            return_value=ProjectContext.WORKSPACE,
        ):
            result = tool.execute(
                path=str(tmp_path),
                member="existing-pkg",
                org="myorg",
                author="Author",
                email="a@b.com",
            )
        assert result.success is False
        assert "already exists" in (result.error or "")

    def test_member_not_in_workspace(self, tmp_path: Path) -> None:
        """Not inside a workspace → ToolResult(success=False)."""
        from axm_init.checks._workspace import ProjectContext
        from axm_init.tools.scaffold import InitScaffoldTool

        tool = InitScaffoldTool()
        with patch(
            "axm_init.checks._workspace.detect_context",
            return_value=ProjectContext.STANDALONE,
        ):
            result = tool.execute(
                path=str(tmp_path),
                member="new-pkg",
                org="myorg",
                author="Author",
                email="a@b.com",
            )
        assert result.success is False
        assert "Not inside a UV workspace" in (result.error or "")

    def test_member_scaffold_failure(self, tmp_path: Path) -> None:
        """Copier returns failure → ToolResult(success=False)."""
        from axm_init.checks._workspace import ProjectContext
        from axm_init.tools.scaffold import InitScaffoldTool

        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        )

        mock_copier = MagicMock()
        mock_copier.return_value.copy.return_value = MagicMock(
            success=False, message="copy failed", files_created=[]
        )

        tool = InitScaffoldTool()
        with (
            patch(
                "axm_init.checks._workspace.detect_context",
                return_value=ProjectContext.WORKSPACE,
            ),
            patch("axm_init.adapters.copier.CopierAdapter", mock_copier),
            patch(
                "axm_init.core.templates.get_template_path",
                return_value=Path("/fake/template"),
            ),
        ):
            result = tool.execute(
                path=str(tmp_path),
                member="new-pkg",
                org="myorg",
                author="Author",
                email="a@b.com",
            )
        assert result.success is False
        assert "copy failed" in (result.error or "")
