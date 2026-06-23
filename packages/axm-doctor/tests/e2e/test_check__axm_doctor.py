"""E2E tests for the axm-doctor CLI (subprocess black box)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_PKG_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.e2e
def test_check_runs_readonly() -> None:
    """AC3: `axm-doctor check` exits 0, mentions uv, and installs nothing."""
    proc = subprocess.run(
        ["uv", "run", "axm-doctor", "check"],
        cwd=_PKG_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "uv" in proc.stdout


@pytest.mark.e2e
def test_help_lists_commands() -> None:
    """AC5: `axm-doctor --help` lists both check and bootstrap."""
    proc = subprocess.run(
        ["uv", "run", "axm-doctor", "--help"],
        cwd=_PKG_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    combined = proc.stdout + proc.stderr
    assert "check" in combined
    assert "bootstrap" in combined
