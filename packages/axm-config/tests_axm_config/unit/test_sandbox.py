from __future__ import annotations

import importlib
import os
import re
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

from axm_config import paths, profile

_SANDBOX_KEYS = (
    "AXM_SANDBOX_ROOT",
    "AXM_SANDBOX_LAUNCH_HOME",
    "AXM_SANDBOX_LAUNCH_PROFILE",
    "AXM_SANDBOX_LAUNCH_AXM_HOME",
)
_CLEARED_KEYS = (
    *_SANDBOX_KEYS,
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
    """Snapshot os.environ, clear AXM state keys and point HOME at a tmp path."""
    saved = dict(os.environ)
    for key in _CLEARED_KEYS:
        os.environ.pop(key, None)
    fake_home = tmp_path.resolve() / "home"
    os.environ["HOME"] = str(fake_home)
    try:
        yield fake_home
    finally:
        os.environ.clear()
        os.environ.update(saved)


def test_activation_publishes_the_sandbox_and_strips_axm_profile(
    home: Path, tmp_path: Path
) -> None:
    """AC1: activation publishes the sandbox, strips AXM_PROFILE, restores it."""
    sandbox_mod = _sandbox()
    root = tmp_path.resolve() / "sbx"
    os.environ["AXM_PROFILE"] = "dev"

    handle = sandbox_mod.activate_sandbox(root)

    assert os.environ["AXM_SANDBOX_ROOT"] == str(root)
    assert "AXM_PROFILE" not in os.environ
    active = sandbox_mod.active_sandbox()
    assert active is not None
    assert active.root == root
    assert active.launch_profile == "dev"
    assert profile.current_profile() == "dev"

    sandbox_mod.deactivate_sandbox(handle)

    assert os.environ["AXM_PROFILE"] == "dev"
    assert not [key for key in os.environ if key.startswith("AXM_SANDBOX_")]
    assert sandbox_mod.active_sandbox() is None


@pytest.mark.parametrize(
    ("variable", "relative"),
    [
        ("AXM_TICKETS_DB_PATH", Path("axm") / "tickets" / "tickets.db"),
        ("AXM_PATHS_SESSIONS_ROOT", Path(".axm") / "sessions-leak"),
    ],
)
def test_escaping_launch_variables_are_refused_by_name(
    home: Path, tmp_path: Path, variable: str, relative: Path
) -> None:
    """AC2: a launch variable under HOME/axm or HOME/.axm is refused by name."""
    sandbox_mod = _sandbox()
    os.environ[variable] = str(home / relative)

    with pytest.raises(sandbox_mod.SandboxEscapeError, match=re.escape(variable)):
        sandbox_mod.activate_sandbox(tmp_path.resolve() / "sbx")


@pytest.mark.parametrize("launch_profile", [None, "production", "dev"])
def test_six_resolvers_land_under_the_sandbox_root(
    home: Path, tmp_path: Path, launch_profile: str | None
) -> None:
    """AC3: the six state resolvers return distinct paths under the root."""
    sandbox_mod = _sandbox()
    if launch_profile is not None:
        os.environ["AXM_PROFILE"] = launch_profile
    root = tmp_path.resolve() / "sbx"
    sandbox_mod.activate_sandbox(root)

    resolved = [
        paths.sessions_root(),
        paths.quality_dir(),
        paths.protocols_dir(),
        paths.tickets_db(),
        paths.warden_socket(),
        paths.warden_log_path(),
    ]

    assert all(path.is_relative_to(root) for path in resolved), resolved
    assert len(set(resolved)) == len(resolved)
