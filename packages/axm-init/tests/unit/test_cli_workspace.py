"""Unit tests for CLI workspace scaffold subcommands (AXM-308).

Tests all workspace-related CLI behaviors:
- AC1: --workspace flag invokes workspace scaffold
- AC3: --workspace and --member are mutually exclusive
- AC4: Default scaffold (no flags) still works for standalone
- AC6: --member outside workspace prints error
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


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

        call_args = mock_copier.copy.call_args[0][0]
        assert "workspace" in str(call_args.template_path).lower()


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
