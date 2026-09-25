from __future__ import annotations

import importlib
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.e2e

_CLEARED_KEYS = (
    "AXM_SANDBOX_ROOT",
    "AXM_SANDBOX_LAUNCH_HOME",
    "AXM_SANDBOX_LAUNCH_PROFILE",
    "AXM_SANDBOX_LAUNCH_AXM_HOME",
    "AXM_PROFILE",
    "AXM_HOME",
    "AXM_WARDEN_SOCKET",
    "AXM_PATHS_SESSIONS_ROOT",
    "AXM_PATHS_QUALITY_DIR",
    "AXM_PATHS_PROTOCOLS_DIR",
    "AXM_PATHS_WARDEN_SOCKET",
    "AXM_TICKETS_DB_PATH",
    "AXM_WARDEN_LOG_PATH",
)
_CHILD = "from axm_config.paths import sessions_root; print(sessions_root())"


def _sandbox() -> ModuleType:
    """Import the sandbox module lazily so its absence fails inside the test."""
    return importlib.import_module("axm_config.sandbox")


@pytest.fixture
def home(tmp_path: Path) -> Iterator[Path]:
    """Snapshot os.environ, clear AXM state keys and point HOME at a tmp dir."""
    saved = dict(os.environ)
    for key in _CLEARED_KEYS:
        os.environ.pop(key, None)
    fake_home = tmp_path.resolve() / "home"
    fake_home.mkdir()
    os.environ["HOME"] = str(fake_home)
    try:
        yield fake_home
    finally:
        os.environ.clear()
        os.environ.update(saved)


def test_child_interpreter_inherits_the_sandbox(home: Path, tmp_path: Path) -> None:
    """AC9: a child python -c spawned with the sandbox environ stays under R."""
    sandbox_mod = _sandbox()
    os.environ["AXM_PROFILE"] = "dev"
    root = tmp_path.resolve() / "sbx"
    sandbox_mod.activate_sandbox(root)

    completed = subprocess.run(
        [sys.executable, "-c", _CHILD],
        env=dict(os.environ),
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    printed = Path(completed.stdout.strip())
    assert printed.is_relative_to(root)
    assert not printed.is_relative_to(home / "axm")
    assert not printed.is_relative_to(home / ".axm")
