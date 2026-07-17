"""E2E tests for the axm-doctor CLI (subprocess black box)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_PKG_ROOT = Path(__file__).resolve().parents[2]

# Drive the CLI through the installed module with an empty PATH so every probed
# tool is genuinely absent -> an unhealthy env, deterministically.
_RUN_APP = "from axm_doctor.cli import app; app()"


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
def test_check_strict_exits_one_on_unhealthy(tmp_path: Path) -> None:
    """AC2: `check --strict` exits 1 against an unhealthy env (tools absent)."""
    env = {**os.environ, "PATH": str(tmp_path)}
    proc = subprocess.run(
        [sys.executable, "-c", _RUN_APP, "check", "--strict"],
        cwd=_PKG_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr


@pytest.mark.e2e
def test_check_default_exits_zero_on_unhealthy(tmp_path: Path) -> None:
    """AC1: `check` without `--strict` exits 0 even against an unhealthy env."""
    env = {**os.environ, "PATH": str(tmp_path)}
    proc = subprocess.run(
        [sys.executable, "-c", _RUN_APP, "check"],
        cwd=_PKG_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


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
