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


@pytest.mark.parametrize("launch_profile", [None, "dev"])
def test_launch_sessions_root_override_is_honoured(
    home: Path, tmp_path: Path, launch_profile: str | None
) -> None:
    """AC4: a launch AXM_PATHS_SESSIONS_ROOT outside HOME state is honoured."""
    sandbox_mod = _sandbox()
    override = tmp_path / "x"
    override.mkdir()
    os.environ["AXM_PATHS_SESSIONS_ROOT"] = str(override)
    if launch_profile is not None:
        os.environ["AXM_PROFILE"] = launch_profile
    sandbox_mod.activate_sandbox(tmp_path.resolve() / "sbx")

    assert paths.sessions_root() == override.resolve()


@pytest.mark.parametrize("launch_profile", [None, "production"])
def test_test_set_dev_profile_restores_profile_paths(
    home: Path, tmp_path: Path, launch_profile: str | None
) -> None:
    """AC6: a test-set AXM_PROFILE=dev gives today's dev profile sessions root."""
    sandbox_mod = _sandbox()
    if launch_profile is not None:
        os.environ["AXM_PROFILE"] = launch_profile
    sandbox_mod.activate_sandbox(tmp_path.resolve() / "sbx")
    os.environ["AXM_PROFILE"] = "dev"

    expected = home / ".axm" / "profiles" / "dev" / "sessions"
    assert paths.sessions_root() == expected.resolve()


def test_test_set_same_production_profile_restores_production_paths(
    home: Path, tmp_path: Path
) -> None:
    """AC6: re-setting AXM_PROFILE=production gives the production root."""
    sandbox_mod = _sandbox()
    os.environ["AXM_PROFILE"] = "production"
    sandbox_mod.activate_sandbox(tmp_path.resolve() / "sbx")
    os.environ["AXM_PROFILE"] = "production"

    assert paths.sessions_root() == home / "axm" / "sessions"


def test_test_set_home_without_config_restores_home_rules(
    home: Path, tmp_path: Path
) -> None:
    """AC8: a test-set HOME without config gives H/axm/sessions."""
    sandbox_mod = _sandbox()
    sandbox_mod.activate_sandbox(tmp_path.resolve() / "sbx")
    new_home = tmp_path.resolve() / "h"
    new_home.mkdir()
    os.environ["HOME"] = str(new_home)

    assert paths.sessions_root() == new_home / "axm" / "sessions"


def test_test_set_home_with_config_honours_its_sessions_root(
    home: Path, tmp_path: Path
) -> None:
    """AC8: a test-set HOME whose config.toml sets sessions_root is honoured."""
    sandbox_mod = _sandbox()
    sandbox_mod.activate_sandbox(tmp_path.resolve() / "sbx")
    new_home = tmp_path.resolve() / "h"
    (new_home / ".axm").mkdir(parents=True)
    target = tmp_path / "z"
    (new_home / ".axm" / "config.toml").write_text(
        f'[paths]\nsessions_root = "{target}"\n', encoding="utf-8"
    )
    os.environ["HOME"] = str(new_home)

    assert paths.sessions_root() == target.resolve()
