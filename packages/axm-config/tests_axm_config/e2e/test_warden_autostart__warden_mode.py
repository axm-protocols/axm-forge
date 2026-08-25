"""Black-box subprocess coverage for warden configuration resolution."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


def _subprocess_env(tmp_path: Path, **warden_values: str) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("AXM_WARDEN_")
    }
    env["HOME"] = str(tmp_path)
    env["AXM_HOME"] = str(tmp_path / ".axm")
    env.update(
        {f"AXM_WARDEN_{key.upper()}": value for key, value in warden_values.items()}
    )
    return env


@pytest.mark.e2e
def test_mode_and_autostart_resolve_in_a_fresh_interpreter(tmp_path: Path) -> None:
    """AC3, AC4: typed environment values cross the package public boundary."""
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import axm_config; "
                "print(axm_config.warden_mode(), axm_config.warden_autostart())"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=_subprocess_env(tmp_path, mode="pull", autostart="false"),
    )

    assert completed.returncode == 0
    assert completed.stdout.strip() == "pull False"


@pytest.mark.e2e
def test_invalid_mode_fails_a_fresh_interpreter_loudly(tmp_path: Path) -> None:
    """AC4: an invalid configured mode surfaces ConfigError to the process."""
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import axm_config; axm_config.warden_mode()",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=_subprocess_env(tmp_path, mode="daemon"),
    )

    assert completed.returncode != 0
    assert "ConfigError" in completed.stderr
