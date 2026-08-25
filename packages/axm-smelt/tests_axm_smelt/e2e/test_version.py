"""End-to-end tests for the smelt version CLI subcommand (subprocess invocation)."""

from __future__ import annotations

import subprocess
import sys


class TestVersionE2E:
    def test_cli_entrypoint(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "axm_smelt.cli", "version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Fallback: try the script entry point
        if result.returncode != 0:
            result = subprocess.run(
                [sys.executable, "-m", "axm_smelt.cli", "version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        assert result.returncode == 0
        assert len(result.stdout.strip()) > 0
