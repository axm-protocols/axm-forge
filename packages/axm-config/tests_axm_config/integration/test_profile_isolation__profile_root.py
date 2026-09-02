from __future__ import annotations

from pathlib import Path

import pytest

import axm_config

__all__: list[str] = []

_EXPECTED_PATH_KEYS = {
    "tickets_db",
    "warden_socket",
    "warden_log",
    "sessions_root",
    "quality_dir",
    "protocols_dir",
}


@pytest.mark.integration
def test_profile_isolation_resolves_explicit_profile_without_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AC3: résout les six chemins absolus du profil explicite."""
    monkeypatch.setenv("AXM_HOME", str(tmp_path))
    monkeypatch.delenv("AXM_PROFILE", raising=False)

    result = axm_config.profile_isolation("scratch")

    assert result.profile == "scratch"
    assert result.profile_root == tmp_path / "profiles" / "scratch"
    assert set(result.paths) == _EXPECTED_PATH_KEYS
    assert all(path.is_absolute() for path in result.paths.values())


@pytest.mark.integration
def test_profile_isolation_reports_fully_contained_profile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AC3: rend un verdict isolé lorsque les six chemins sont contenus."""
    monkeypatch.setenv("AXM_HOME", str(tmp_path))
    monkeypatch.delenv("AXM_PROFILE", raising=False)

    result = axm_config.profile_isolation("scratch")

    assert result.isolated is True
    assert result.escapes == []


@pytest.mark.integration
def test_profile_isolation_does_not_create_missing_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AC4: ne matérialise pas le répertoire AXM_HOME absent."""
    missing_home = tmp_path / "home"
    monkeypatch.setenv("AXM_HOME", str(missing_home))
    monkeypatch.delenv("AXM_PROFILE", raising=False)

    axm_config.profile_isolation("scratch")

    assert missing_home.exists() is False
    assert list(tmp_path.iterdir()) == []
