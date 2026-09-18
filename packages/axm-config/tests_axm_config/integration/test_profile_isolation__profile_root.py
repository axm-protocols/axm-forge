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
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("AXM_HOME", str(tmp_path))
    monkeypatch.delenv("AXM_PROFILE", raising=False)

    result = axm_config.profile_isolation("scratch")

    assert result.profile == "scratch"
    assert result.profile_root == axm_config.profile_root_for("scratch")
    assert set(result.paths) == _EXPECTED_PATH_KEYS
    assert result.paths == {
        "tickets_db": axm_config.tickets_db(profile="scratch"),
        "warden_socket": axm_config.warden_socket(profile="scratch"),
        "warden_log": axm_config.warden_log_path(profile="scratch"),
        "sessions_root": axm_config.sessions_root(profile="scratch"),
        "quality_dir": axm_config.quality_dir(profile="scratch"),
        "protocols_dir": axm_config.protocols_dir(profile="scratch"),
    }
    assert result.isolated is True
    assert result.escapes == []


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


@pytest.mark.integration
def test_profile_isolation_default_profile_mirrors_resolver_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AC1: chaque emplacement du profil par defaut reflete le resolveur."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AXM_HOME", raising=False)
    monkeypatch.delenv("AXM_PROFILE", raising=False)

    result = axm_config.profile_isolation()

    assert result.paths == {
        "tickets_db": axm_config.tickets_db(),
        "warden_socket": axm_config.warden_socket(),
        "warden_log": axm_config.warden_log_path(),
        "sessions_root": axm_config.sessions_root(),
        "quality_dir": axm_config.quality_dir(),
        "protocols_dir": axm_config.protocols_dir(),
    }


@pytest.mark.integration
def test_profile_isolation_default_profile_reports_every_location_as_escape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AC2: le profil par defaut n'est pas isole et liste ses six echappees."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AXM_HOME", raising=False)
    monkeypatch.delenv("AXM_PROFILE", raising=False)

    result = axm_config.profile_isolation()

    assert result.isolated is False
    assert result.escapes == [
        "protocols_dir",
        "quality_dir",
        "sessions_root",
        "tickets_db",
        "warden_log",
        "warden_socket",
    ]


@pytest.mark.integration
def test_profile_isolation_reports_configured_location_as_escape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AC4: un emplacement configure hors profil est rapporte et compte echappe."""
    home = tmp_path / "home"
    home.mkdir()
    axm_home = tmp_path / "axm-home"
    axm_home.mkdir()
    configured = tmp_path / "elsewhere" / "sessions"
    (axm_home / "config.toml").write_text(
        f'[paths]\nsessions_root = "{configured}"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("AXM_HOME", str(axm_home))
    monkeypatch.delenv("AXM_PROFILE", raising=False)

    result = axm_config.profile_isolation()

    assert result.paths["sessions_root"] == configured.resolve()
    assert "sessions_root" in result.escapes
