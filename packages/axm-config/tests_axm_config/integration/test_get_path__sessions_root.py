"""Integration coverage for profile-root containment of configured state paths."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

import axm_config
from axm_config import (
    ConfigError,
    get_path,
    protocols_dir,
    quality_dir,
    sessions_root,
    tickets_db,
    warden_log_path,
    warden_socket,
)

pytestmark = pytest.mark.integration


def _select_dev_profile(
    home: Path,
    monkeypatch: pytest.MonkeyPatch,
    document: str,
) -> None:
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("AXM_HOME", str(home / ".axm"))
    monkeypatch.setenv("AXM_PROFILE", "dev")
    config_path = home / ".axm" / "profiles" / "dev" / "config.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(document, encoding="utf-8")


def test_every_state_accessor_refuses_a_configured_path_outside_its_profile_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1: all six state accessors reject configured paths outside dev."""
    outside = Path("/tmp/outside/state").resolve()
    _select_dev_profile(
        tmp_path,
        monkeypatch,
        (
            "[tickets]\n"
            'db_path = "/tmp/outside/state"\n'
            "[warden]\n"
            'log_path = "/tmp/outside/state"\n'
            "[paths]\n"
            'warden_socket = "/tmp/outside/state"\n'
            'sessions_root = "/tmp/outside/state"\n'
            'quality_dir = "/tmp/outside/state"\n'
            'protocols_dir = "/tmp/outside/state"\n'
        ),
    )
    accessors: tuple[Callable[[], Path], ...] = (
        tickets_db,
        warden_socket,
        warden_log_path,
        sessions_root,
        quality_dir,
        protocols_dir,
    )

    for accessor in accessors:
        with pytest.raises(ConfigError) as exc_info:
            accessor()
        diagnostic = str(exc_info.value)
        assert "dev" in diagnostic
        assert str(outside) in diagnostic


def test_path_under_another_profile_root_is_a_containment_violation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: dev cannot resolve state from the staging profile root."""
    _select_dev_profile(
        tmp_path,
        monkeypatch,
        ('[paths]\nsessions_root = "~/.axm/profiles/staging/sessions"\n'),
    )

    with pytest.raises(ConfigError):
        sessions_root()


def test_get_path_itself_guards_non_production_profile_containment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: generic get_path rejects configured values outside dev."""
    outside = Path("/tmp/outside/x").resolve()
    _select_dev_profile(
        tmp_path,
        monkeypatch,
        ('[custom]\nstate_path = "/tmp/outside/x"\n'),
    )

    with pytest.raises(ConfigError) as exc_info:
        get_path("state_path", default=Path("/unused"), namespace="custom")

    diagnostic = str(exc_info.value)
    assert "dev" in diagnostic
    assert str(outside) in diagnostic


def _bare_production_home(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Select the production profile on a HOME holding no ``.axm`` yet."""
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AXM_HOME", raising=False)
    monkeypatch.delenv("AXM_PROFILE", raising=False)
    monkeypatch.delenv("AXM_PATHS_SESSIONS_ROOT", raising=False)


def test_get_path_applies_the_requested_profile_convention(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: a named profile roots the state path even when none is active."""
    _bare_production_home(tmp_path, monkeypatch)

    result = get_path(
        "sessions_root",
        default=tmp_path / "caller" / "sessions",
        profile="scratch",
    )

    scratch_root = axm_config.axm_home_path() / "profiles" / "scratch"
    assert result == scratch_root / "sessions"


def test_get_path_returns_the_caller_default_for_the_production_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: requesting production ignores the active non-default profile."""
    _bare_production_home(tmp_path, monkeypatch)
    monkeypatch.setenv("AXM_PROFILE", "scratch")
    caller_default = tmp_path / "caller" / "sessions"

    result = get_path(
        "sessions_root",
        default=caller_default,
        profile="production",
    )

    assert result == caller_default


def test_get_path_guards_containment_against_the_requested_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC6: a configured path outside the requested profile root is refused."""
    outside = Path("/tmp/outside/scratch-state").resolve()
    _bare_production_home(tmp_path, monkeypatch)
    monkeypatch.setenv("AXM_HOME", str(tmp_path / ".axm"))
    config_path = tmp_path / ".axm" / "config.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        '[paths]\nsessions_root = "/tmp/outside/scratch-state"\n',
        encoding="utf-8",
    )

    with pytest.raises(ConfigError) as exc_info:
        get_path(
            "sessions_root",
            default=tmp_path / "caller" / "sessions",
            profile="scratch",
        )

    diagnostic = str(exc_info.value)
    assert "scratch" in diagnostic
    assert str(outside) in diagnostic


def test_get_path_does_not_materialise_the_axm_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC8: reading the configuration layer never creates the AXM home."""
    _bare_production_home(tmp_path, monkeypatch)
    caller_default = tmp_path / "caller" / "sessions"

    result = get_path("sessions_root", default=caller_default)

    assert result == caller_default
    assert not (tmp_path / ".axm").exists()
