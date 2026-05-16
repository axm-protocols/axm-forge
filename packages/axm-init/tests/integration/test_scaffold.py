"""Integration tests for CLI workspace scaffold subcommands (AXM-308)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


class TestCliScaffoldMember:
    """AC2: --member <name> invokes member scaffold."""

    def test_cli_scaffold_member(
        self, workspace_root__from_cli_workspace_scaffold_subcommands: Path
    ) -> None:
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
                str(workspace_root__from_cli_workspace_scaffold_subcommands),
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
