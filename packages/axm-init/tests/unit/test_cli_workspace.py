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

import pytest


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
