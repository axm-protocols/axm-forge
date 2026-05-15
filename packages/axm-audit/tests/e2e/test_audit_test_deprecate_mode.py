"""E2E test for axm-audit `test` CLI: --mode flag absent from --help."""

from __future__ import annotations

import subprocess
import sys


class TestCliNoModeFlag:
    def test_cli_no_mode_flag(self):
        """CLI 'test --help' must not expose a --mode flag."""
        proc = subprocess.run(
            [sys.executable, "-m", "axm_audit", "test", "--help"],
            capture_output=True,
            text=True,
        )
        assert "--mode" not in proc.stdout, "--mode flag should be removed from CLI"
