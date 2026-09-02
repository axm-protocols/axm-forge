"""Integration between AXM home resolution and profile paths."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

import pytest

from axm_config import axm_home


def _profile_module() -> ModuleType:
    return importlib.import_module("axm_config.profile")


@pytest.mark.integration
def test_profile_root_is_nested_under_axm_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3: a development profile is rooted below ~/.axm/profiles."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("AXM_PROFILE", "dev")

    home = axm_home()

    assert _profile_module().profile_root() == home / "profiles" / "dev"


@pytest.mark.integration
def test_production_profile_has_no_profile_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3: production exposes no separate profile root."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("AXM_PROFILE", raising=False)

    axm_home()

    assert _profile_module().profile_root() is None


@pytest.mark.integration
def test_profile_config_path_is_nested_under_profile_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC4: a development profile stores config below its profile root."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("AXM_PROFILE", "dev")

    home = axm_home()

    assert (
        _profile_module().profile_config_path()
        == home / "profiles" / "dev" / "config.toml"
    )
