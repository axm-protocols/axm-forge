"""E2E hermeticity guard: git-identity config reads zero machine state.

Runs the ``load_config`` integration suite in a **scrubbed** subprocess
(``env -i`` style: only ``HOME`` -> a fresh tmp dir and ``PATH`` survive — no
ambient ``~/.axm`` store, no ``AXM_*`` override, no global git config),
reproducing the CI-like hermetic environment of AC1/AC3. A green child exit
proves those tests source their config solely from the tmp store they build,
never from the developer machine — the regression that made ``load_config()``
return ``None`` only on clean runners can no longer hide.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

_TARGET = "tests/integration/test_identity__load_config.py"


def test_load_config_suite_green_under_scrubbed_env() -> None:
    """AC1/AC3: the resolution tests pass with an empty HOME and no machine state."""
    package_root = Path(__file__).resolve().parents[2]
    scrubbed_env = {"HOME": tempfile.mkdtemp(), "PATH": os.environ["PATH"]}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            _TARGET,
            "-o",
            "addopts=",
            "-p",
            "no:cacheprovider",
            "-q",
        ],
        cwd=package_root,
        env=scrubbed_env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
