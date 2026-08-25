"""Black-box coverage for typed configuration helpers."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def test_environment_bool_coercion_in_fresh_interpreter(tmp_path: Path) -> None:
    """AC3: false-ish environment text is coerced across the package boundary."""
    config_home = tmp_path / "axm-home"
    config_home.mkdir()
    env = os.environ.copy()
    env["AXM_HOME"] = str(config_home)
    env["AXM_WARDEN_AUTOSTART"] = "false"

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from axm_config import get_bool; "
                "print(get_bool('autostart', True, namespace='warden'))"
            ),
        ],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "False"


def test_environment_int_coercion_in_fresh_interpreter(tmp_path: Path) -> None:
    """AC2: numeric environment text behaves as an int across the public API."""
    config_home = tmp_path / "axm-home"
    config_home.mkdir()
    env = os.environ.copy()
    env["AXM_HOME"] = str(config_home)
    env["AXM_WARDEN_MAX_CONCURRENT"] = "6"

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from axm_config import get_int; "
                "print(get_int('max_concurrent', 4, namespace='warden') + 1)"
            ),
        ],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "7"
