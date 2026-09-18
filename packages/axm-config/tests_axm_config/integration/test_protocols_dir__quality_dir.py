"""Integration coverage for named-profile work roots and non-creating reads."""

from __future__ import annotations

from pathlib import Path

import pytest

import axm_config

pytestmark = pytest.mark.integration

_PATH_ENV_KEYS = (
    "AXM_PATHS_PROTOCOLS_DIR",
    "AXM_PATHS_QUALITY_DIR",
    "AXM_WARDEN_LOG_PATH",
)


@pytest.fixture
def bare_production_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Select the production profile on a HOME holding no ``.axm`` yet."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("AXM_HOME", raising=False)
    monkeypatch.delenv("AXM_PROFILE", raising=False)
    for key in _PATH_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    return tmp_path


def test_state_accessors_answer_for_a_named_profile(
    bare_production_home: Path,
) -> None:
    """AC5: quality, protocols and the warden log answer for scratch."""
    quality = axm_config.quality_dir(profile="scratch")
    protocols = axm_config.protocols_dir(profile="scratch")
    log_path = axm_config.warden_log_path(profile="scratch")

    scratch_root = axm_config.axm_home_path() / "profiles" / "scratch"
    assert quality == scratch_root / "quality"
    assert protocols == scratch_root / "protocols"
    assert log_path == scratch_root / "warden.log"


def test_warden_log_path_does_not_materialise_the_axm_home(
    bare_production_home: Path,
) -> None:
    """AC7: computing the warden log location creates no AXM home."""
    result = axm_config.warden_log_path()

    assert result == (bare_production_home / ".axm").resolve() / "warden.log"
    assert not (bare_production_home / ".axm").exists()
