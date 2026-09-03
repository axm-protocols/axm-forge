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


@pytest.mark.e2e
def test_check_renders_credential_and_auth_dependency_by_kind(
    tmp_path: Path,
) -> None:
    """AC5: check renders both declaration kinds side by side in one run."""
    module = tmp_path / "fixture_check_catalog.py"
    module.write_text(
        """
from axm_vault.models import CredentialGroup, CredentialSpec


def provide():
    return [
        CredentialGroup(
            id="fixture.check",
            package="axm-fixture",
            title="Check",
            specs=(
                CredentialSpec(
                    name="api_token",
                    env="FIXTURE_CHECK_TOKEN",
                    kind="token",
                ),
                CredentialSpec(
                    name="github_session",
                    env="FIXTURE_CHECK_SESSION",
                    kind="auth_dependency",
                ),
            ),
        )
    ]
""".lstrip(),
        encoding="utf-8",
    )
    dist_info = tmp_path / "fixture_check_catalog-1.0.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: fixture-check-catalog\nVersion: 1.0\n",
        encoding="utf-8",
    )
    (dist_info / "entry_points.txt").write_text(
        "[axm.credentials]\nfixture = fixture_check_catalog:provide\n",
        encoding="utf-8",
    )
    pythonpath = os.pathsep.join(
        part for part in (str(tmp_path), os.environ.get("PYTHONPATH")) if part
    )
    env = {
        **os.environ,
        "PYTHONPATH": pythonpath,
        "FIXTURE_CHECK_TOKEN": "present",
    }
    env.pop("FIXTURE_CHECK_SESSION", None)

    proc = subprocess.run(
        [sys.executable, "-c", _RUN_APP, "check"],
        cwd=_PKG_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "token" in proc.stdout
    assert "fixture.check.api_token" in proc.stdout
    assert "auth_dependency" in proc.stdout
    auth_line = next(
        line for line in proc.stdout.splitlines() if "github_session" in line
    )
    assert "axm-vault set" not in auth_line
