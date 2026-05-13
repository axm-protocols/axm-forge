"""Functional tests for CLI workspace scaffold subcommands (AXM-308).

Tests all workspace-related CLI behaviors:
- AC1: --workspace flag invokes workspace scaffold
- AC2: --member <name> invokes member scaffold
- AC3: --workspace and --member are mutually exclusive
- AC4: Default scaffold (no flags) still works for standalone
- AC5: check output shows context
- AC6: --member outside workspace prints error
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def workspace_root(tmp_path: Path) -> Path:
    """Create a minimal workspace structure for tests."""
    ws = tmp_path / "test-ws"
    ws.mkdir()
    (ws / "pyproject.toml").write_text(
        '[project]\nname = "test-ws"\n\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
    )
    (ws / "Makefile").write_text("test-all:\n\techo test\n")
    (ws / "mkdocs.yml").write_text("site_name: test\nnav:\n  - Home: index.md\n")
    ci_dir = ws / ".github" / "workflows"
    ci_dir.mkdir(parents=True)
    (ci_dir / "ci.yml").write_text(
        "jobs:\n  test:\n    strategy:\n      matrix:\n"
        "        package:\n          - existing\n"
        "    steps:\n      - run: echo test\n"
    )
    (ci_dir / "publish.yml").write_text(
        "name: Publish\non:\n  push:\n"
        "    tags:\n"
        '      - "v*"\n'
        "jobs:\n  pub:\n    runs-on: ubuntu-latest\n"
    )
    (ws / "packages").mkdir()
    return ws


class TestCliScaffoldWorkspace:
    """AC1: --workspace invokes workspace scaffold."""

    def test_cli_scaffold_workspace(self, tmp_path: Path) -> None:
        """scaffold --workspace routes to workspace template."""
        from axm_init.cli import scaffold

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.files_created = [tmp_path / "pyproject.toml"]
        mock_result.message = ""

        with patch("axm_init.adapters.copier.CopierAdapter") as mock_cls:
            mock_copier = MagicMock()
            mock_copier.copy.return_value = mock_result
            mock_cls.return_value = mock_copier

            scaffold(
                str(tmp_path),
                name="test-ws",
                org="test-org",
                author="Test",
                email="test@test.com",
                workspace=True,
            )

        # Verify workspace template was used
        call_args = mock_copier.copy.call_args[0][0]
        assert "workspace" in str(call_args.template_path).lower()


class TestCliScaffoldMember:
    """AC2: --member <name> invokes member scaffold."""

    def test_cli_scaffold_member(self, workspace_root: Path) -> None:
        """scaffold --member pkg creates member inside workspace."""
        from axm_init.cli import scaffold

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.files_created = [Path("pyproject.toml")]
        mock_result.message = ""

        with patch("axm_init.adapters.copier.CopierAdapter") as mock_cls:
            mock_copier = MagicMock()
            mock_copier.copy.return_value = mock_result
            mock_cls.return_value = mock_copier

            scaffold(
                str(workspace_root),
                org="test-org",
                author="Test",
                email="test@test.com",
                member="my-pkg",
            )

        # Verify member template was used for packages/my-pkg
        call_args = mock_copier.copy.call_args[0][0]
        dest = str(call_args.destination)
        assert "packages" in dest
        assert "my-pkg" in dest


class TestCliScaffoldMutualExclusive:
    """AC3: --workspace and --member are mutually exclusive."""

    def test_cli_scaffold_mutual_exclusive(self, tmp_path: Path) -> None:
        """Error when both --workspace and --member are given."""
        from axm_init.cli import scaffold

        with pytest.raises(SystemExit, match="1"):
            scaffold(
                str(tmp_path),
                org="test-org",
                author="Test",
                email="test@test.com",
                workspace=True,
                member="foo",
            )


class TestCliScaffoldDefaultUnchanged:
    """AC4: Default scaffold (no flags) uses standalone template."""

    def test_cli_scaffold_default_unchanged(self, tmp_path: Path) -> None:
        """Default scaffold produces standalone package."""
        from axm_init.cli import scaffold

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.files_created = [tmp_path / "pyproject.toml"]
        mock_result.message = ""

        with patch("axm_init.adapters.copier.CopierAdapter") as mock_cls:
            mock_copier = MagicMock()
            mock_copier.copy.return_value = mock_result
            mock_cls.return_value = mock_copier

            scaffold(
                str(tmp_path),
                name="test-project",
                org="test-org",
                author="Test",
                email="test@test.com",
            )

        call_args = mock_copier.copy.call_args[0][0]
        assert "python-project" in str(call_args.template_path).lower()


class TestCliCheckShowsContext:
    """AC5: check output header shows context."""

    def test_cli_check_shows_context(self, workspace_root: Path, capsys: Any) -> None:
        """check on workspace shows 'Context: WORKSPACE'."""
        from axm_init.core.checker import CheckEngine

        engine = CheckEngine(workspace_root)
        result = engine.run()

        from axm_init.core.checker import format_report

        report = format_report(result)
        assert "Context:" in report
        assert "WORKSPACE" in report

    def test_format_agent_has_context(self, workspace_root: Path) -> None:
        """Agent output includes context field."""
        from axm_init.core.checker import CheckEngine, format_agent

        engine = CheckEngine(workspace_root)
        result = engine.run()
        agent_output = format_agent(result)

        assert "context" in agent_output
        assert agent_output["context"] == "workspace"


class TestCliMemberOutsideWorkspace:
    """AC6: --member outside workspace prints error."""

    def test_cli_member_outside_workspace(self, tmp_path: Path) -> None:
        """Running --member without a workspace exits with error."""
        from axm_init.cli import scaffold

        with pytest.raises(SystemExit, match="1"):
            scaffold(
                str(tmp_path),
                org="test-org",
                author="Test",
                email="test@test.com",
                member="my-pkg",
            )
