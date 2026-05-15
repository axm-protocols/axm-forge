"""End-to-end test for the `axm-init` CLI entry point via subprocess."""

from __future__ import annotations

import subprocess
import sys


class TestEntryPoint:
    """Test that the CLI entry point works via subprocess."""

    def test_cli_entry_point_runs(self) -> None:
        """axm-init --help can be invoked via python -m."""
        result = subprocess.run(
            [sys.executable, "-m", "axm_init.cli", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Should not crash
        assert result.returncode in (0, 2)
