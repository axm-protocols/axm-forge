"""Integration coverage for profile-isolated runtime paths."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

import axm_config

_PROFILE_PATH_ENV_KEYS = (
    "AXM_PATHS_PROTOCOLS_DIR",
    "AXM_PATHS_QUALITY_DIR",
    "AXM_PATHS_SESSIONS_ROOT",
    "AXM_PATHS_WARDEN_SOCKET",
    "AXM_WARDEN_LOG_PATH",
)


@pytest.fixture
def dev_profile_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Activate an isolated development profile with no configured paths."""
    axm_home = tmp_path / ".axm"
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("AXM_HOME", str(axm_home))
    monkeypatch.setenv("AXM_PROFILE", "dev")
    for key in _PROFILE_PATH_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    return axm_home / "profiles" / "dev"


@pytest.mark.integration
@pytest.mark.parametrize(
    "getters",
    [
        (
            axm_config.sessions_root,
            axm_config.quality_dir,
            axm_config.protocols_dir,
        )
    ],
    ids=["work-roots"],
)
def test_work_roots_follow_active_profile(
    getters: tuple[Callable[[], Path], ...],
    dev_profile_root: Path,
) -> None:
    """AC1: every unconfigured work root lives below the active profile."""
    results = [getter() for getter in getters]

    assert all(result.is_relative_to(dev_profile_root) for result in results)


@pytest.mark.integration
@pytest.mark.parametrize(
    "getters",
    [(axm_config.warden_log_path, axm_config.warden_socket)],
    ids=["daemon-runtime-paths"],
)
def test_daemon_runtime_paths_follow_active_profile(
    getters: tuple[Callable[[], Path], ...],
    dev_profile_root: Path,
) -> None:
    """AC2: every unconfigured daemon path lives below the active profile."""
    results = [getter() for getter in getters]

    assert all(result.is_relative_to(dev_profile_root) for result in results)


@pytest.mark.integration
def test_profile_root_overrides_caller_default(dev_profile_root: Path) -> None:
    """AC3: an active profile outranks a caller-supplied socket default."""
    outside = Path("/tmp/outside.sock")

    result = axm_config.warden_socket(default=outside)

    assert result.is_relative_to(dev_profile_root)
    assert result != outside
