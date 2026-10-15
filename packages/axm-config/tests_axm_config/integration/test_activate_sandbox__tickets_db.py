from __future__ import annotations

import importlib
import os
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

from axm_config import paths

pytestmark = pytest.mark.integration

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


def test_per_key_override_hands_back_only_that_key(home: Path, tmp_path: Path) -> None:
    """AC5: a test-set AXM_TICKETS_DB_PATH wins for tickets_db only."""
    sandbox_mod = _sandbox()
    root = tmp_path.resolve() / "sbx"
    sandbox_mod.activate_sandbox(root)
    override = tmp_path / "y.db"
    os.environ["AXM_TICKETS_DB_PATH"] = str(override)

    assert paths.tickets_db() == override.resolve()
    assert paths.sessions_root().is_relative_to(root)


def test_launch_axm_home_config_db_path_is_ignored(home: Path, tmp_path: Path) -> None:
    """AC7: a launch $AXM_HOME/config.toml [tickets].db_path is not honoured."""
    sandbox_mod = _sandbox()
    axm_home = tmp_path / "a"
    axm_home.mkdir()
    leak = home / "axm" / "tickets" / "tickets.db"
    (axm_home / "config.toml").write_text(
        f'[tickets]\ndb_path = "{leak}"\n', encoding="utf-8"
    )
    os.environ["AXM_HOME"] = str(axm_home)
    root = tmp_path.resolve() / "sbx"
    sandbox_mod.activate_sandbox(root)

    assert paths.tickets_db().is_relative_to(root)


def test_test_set_axm_home_without_config_keeps_isolation(
    home: Path, tmp_path: Path
) -> None:
    """AC7: a test-set AXM_HOME without config.toml keeps sessions under root."""
    sandbox_mod = _sandbox()
    root = tmp_path.resolve() / "sbx"
    sandbox_mod.activate_sandbox(root)
    empty = tmp_path / "empty"
    empty.mkdir()
    os.environ["AXM_HOME"] = str(empty)

    assert paths.sessions_root().is_relative_to(root)
