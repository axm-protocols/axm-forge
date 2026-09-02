"""Tests for profile selection and propagation."""

from __future__ import annotations

import importlib
from types import ModuleType

import pytest

from axm_config import ConfigError


def _profile_module() -> ModuleType:
    return importlib.import_module("axm_config.profile")


def test_unset_profile_defaults_to_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1: an unset AXM_PROFILE selects production."""
    monkeypatch.delenv("AXM_PROFILE", raising=False)

    assert _profile_module().current_profile() == "production"


def test_empty_profile_defaults_to_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1: an empty AXM_PROFILE selects production."""
    monkeypatch.setenv("AXM_PROFILE", "")

    assert _profile_module().current_profile() == "production"


def test_profile_name_validation_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: invalid names are rejected and valid names are preserved."""
    invalid_names = ("Dev", "1dev", "dev_x", "-dev", "a" * 33)
    for name in invalid_names:
        monkeypatch.setenv("AXM_PROFILE", name)
        with pytest.raises(ConfigError) as exc_info:
            _profile_module().current_profile()
        assert name in str(exc_info.value)

    for name in ("dev", "ci-2", "a" * 32):
        monkeypatch.setenv("AXM_PROFILE", name)
        assert _profile_module().current_profile() == name


def test_profile_env_propagates_active_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC5: profile_env exports the active profile for a child process."""
    monkeypatch.setenv("AXM_PROFILE", "dev")

    assert _profile_module().profile_env() == {"AXM_PROFILE": "dev"}
