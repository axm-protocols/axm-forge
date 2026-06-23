"""Integration tests for ``load_config`` on the ``config_path=None`` default.

These exercise the new store/echo/legacy resolution path (AC1, AC2, AC3, AC5).
The HOME env is redirected to a tmp dir so both the ``axm_config`` single store
(``~/.axm/config.toml``) and the legacy ``~/axm/git-profiles.toml`` are isolated.
"""

from __future__ import annotations

import logging
from pathlib import Path

import axm_config
import pytest

from axm_git.core.identity import load_config

pytestmark = pytest.mark.integration

_DEFAULT = {"name": "Store Default", "email": "store@example.com"}


@pytest.fixture
def axm_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect HOME to a tmp dir so the store + legacy file are isolated."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("USERPROFILE", raising=False)
    return home


def test_loads_from_store_git_section(axm_home: Path) -> None:
    """AC1: config_path=None builds GitProfileConfig from the [git] store section."""
    axm_config.set_("git", "default", _DEFAULT)
    axm_config.set_(
        "git",
        "profiles",
        {"work": {"name": "Work", "email": "work@example.com"}},
    )
    axm_config.set_("git", "schedule", {"rules": []})

    config = load_config()

    assert config is not None
    assert config.default.name == "Store Default"
    assert config.default.email == "store@example.com"
    assert "work" in config.profiles
    assert config.profiles["work"].email == "work@example.com"


def test_workspace_paths_sourced_from_echo_roots(axm_home: Path) -> None:
    """AC2: workspace_paths comes from [echo].workspace_roots, not [git]."""
    roots = [str(axm_home / "ws-a"), str(axm_home / "ws-b")]
    axm_config.set_("git", "default", _DEFAULT)
    axm_config.set_("echo", "workspace_roots", roots)

    config = load_config()

    assert config is not None
    assert [str(p) for p in config.workspace_paths] == roots


def test_legacy_fallback_when_git_section_absent(
    axm_home: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """AC3: no [git] section but legacy ~/axm/git-profiles.toml present.

    The legacy file is read and a migration WARNING is logged.
    """
    legacy_dir = axm_home / "axm"
    legacy_dir.mkdir()
    legacy = legacy_dir / "git-profiles.toml"
    legacy.write_text('[default]\nname = "Legacy"\nemail = "legacy@example.com"\n')

    with caplog.at_level(logging.WARNING, logger="axm_git.core.identity"):
        config = load_config()

    assert config is not None
    assert config.default.name == "Legacy"
    assert any(
        "migrat" in rec.getMessage().lower() or "legacy" in rec.getMessage().lower()
        for rec in caplog.records
    )


def test_none_when_no_config_anywhere(axm_home: Path) -> None:
    """AC5: no [git] section and no legacy file -> None."""
    config = load_config()
    assert config is None


def test_enabled_flag_round_trips_via_store(axm_home: Path) -> None:
    """AC4: schedule.enabled persists through [git].schedule and is read back.

    Persisting ``enabled=false`` via ``axm_config`` and reading the config
    back through ``load_config`` yields ``schedule.enabled is False``.
    """
    axm_config.set_("git", "default", _DEFAULT)
    axm_config.set_("git", "schedule", {"enabled": False, "rules": []})

    config = load_config()

    assert config is not None
    assert config.schedule.enabled is False
