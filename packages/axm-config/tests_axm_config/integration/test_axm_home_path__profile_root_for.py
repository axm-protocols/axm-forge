"""Integration coverage for the side-effect-free AXM home and profile roots."""

from __future__ import annotations

from pathlib import Path

import pytest

import axm_config

pytestmark = pytest.mark.integration


@pytest.fixture
def bare_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point HOME at a real directory that holds no ``.axm`` yet."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("AXM_HOME", raising=False)
    return tmp_path


def test_axm_home_path_resolves_without_creating_the_directory(
    bare_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1: the pure accessor returns the resolved ~/.axm, creating nothing."""
    monkeypatch.delenv("AXM_PROFILE", raising=False)

    result = axm_config.axm_home_path()

    assert result == (bare_home / ".axm").resolve()
    assert not (bare_home / ".axm").exists()


def test_profile_root_for_answers_for_a_named_profile(
    bare_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: a named profile root is computed whatever AXM_PROFILE holds."""
    monkeypatch.setenv("AXM_PROFILE", "lab")

    production_root = axm_config.profile_root_for("production")
    scratch_root = axm_config.profile_root_for("scratch")

    assert production_root is None
    assert scratch_root == axm_config.axm_home_path() / "profiles" / "scratch"
    assert not (bare_home / ".axm").exists()
