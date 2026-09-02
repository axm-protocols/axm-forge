"""E2E regression guard for the removed module entry point."""

from __future__ import annotations

import subprocess
import sys

import pytest

pytestmark = pytest.mark.e2e


def test_removed_cli_module_cannot_run_as_a_module() -> None:
    """The deleted facade has no executable ``python -m`` entry point."""
    result = subprocess.run(
        [sys.executable, "-m", "axm_init.cli"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "No module named axm_init.cli" in result.stderr
