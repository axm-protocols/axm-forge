"""Coverage tests for tools.scaffold — error paths and edge cases."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


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


class TestScaffoldExecuteException:
    """Cover lines 173-174: exception in execute."""

    def test_copier_exception_caught(self, tmp_path: Path) -> None:
        """Exception from CopierAdapter → ToolResult(success=False)."""
        from axm_init.tools.scaffold import InitScaffoldTool

        tool = InitScaffoldTool()
        with patch(
            "axm_init.adapters.copier.CopierAdapter",
            side_effect=RuntimeError("copier broke"),
        ):
            result = tool.execute(
                path=str(tmp_path),
                org="myorg",
                author="Author",
                email="a@b.com",
            )
        assert result.success is False
        assert "copier broke" in (result.error or "")


class TestScaffoldExecuteMissingTemplate:
    """Cover template error path."""

    def test_get_template_path_error(self, tmp_path: Path) -> None:
        """Non-existent template → exception caught."""
        from axm_init.tools.scaffold import InitScaffoldTool

        tool = InitScaffoldTool()
        with patch(
            "axm_init.core.templates.get_template_path",
            side_effect=FileNotFoundError("template not found"),
        ):
            result = tool.execute(
                path=str(tmp_path),
                org="myorg",
                author="Author",
                email="a@b.com",
            )
        assert result.success is False
        assert "template not found" in (result.error or "")


class TestScaffoldResolveWorkspaceRoot:
    """Cover lines 189, 202: _resolve_workspace_root and _read_workspace_name."""

    def test_resolve_workspace_root_member_context(self, tmp_path: Path) -> None:
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

    def test_resolve_workspace_root_standalone(self, tmp_path: Path) -> None:
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

    def test_read_workspace_name_fallback(self, tmp_path: Path) -> None:
        """No pyproject.toml → falls back to directory name."""
        from axm_init.tools.scaffold import InitScaffoldTool

        result = InitScaffoldTool._read_workspace_name(tmp_path)
        assert result == tmp_path.name

    def test_read_workspace_name_from_toml(self, tmp_path: Path) -> None:
        """Reads name from pyproject.toml."""
        from axm_init.tools.scaffold import InitScaffoldTool

        (tmp_path / "pyproject.toml").write_text('[project]\nname = "my-ws"\n')
        result = InitScaffoldTool._read_workspace_name(tmp_path)
        assert result == "my-ws"


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
