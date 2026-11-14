"""An explicit Studio root owns configuration, profile state and runtime data."""

from pathlib import Path

import pytest

from axm_config.home import axm_home_path, axm_state_path, relocate_runtime_path
from axm_config.paths import sessions_root
from axm_config.profile import profile_config_path, profile_env, profile_root_for
from axm_config.sandbox import activate_sandbox, deactivate_sandbox


def test_central_root_is_pure_and_contains_config_profiles_and_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "AXM"
    monkeypatch.setenv("AXM_ROOT", str(root))
    monkeypatch.delenv("AXM_PROFILE", raising=False)
    assert axm_home_path() == root
    assert profile_config_path() == root / "config.toml"
    assert profile_root_for("dev") == root / "profiles/dev"
    assert axm_state_path("orison") == root / "state/orison"
    assert sessions_root() == root / "data/sessions"
    assert not root.exists()


@pytest.mark.parametrize("value", ["", "relative/path"])
def test_invalid_root_is_refused(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AXM_ROOT", value)
    with pytest.raises(ValueError, match="AXM_ROOT"):
        axm_home_path()


def test_root_cannot_point_inside_source_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.setenv("AXM_ROOT", str(tmp_path / "state"))
    with pytest.raises(ValueError, match="git checkout"):
        axm_home_path()


def test_test_sandbox_strips_and_restores_installation_root(tmp_path: Path) -> None:
    environ = {"HOME": str(tmp_path / "home"), "AXM_ROOT": str(tmp_path / "AXM")}
    original = environ.copy()
    sandbox = activate_sandbox(tmp_path / "sandbox", environ)
    assert "AXM_ROOT" not in environ
    deactivate_sandbox(sandbox, environ)
    assert environ == original


def test_legacy_session_paths_map_without_changing_historical_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    root = home / "AXM"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("AXM_ROOT", str(root))
    original = str(home / "axm/sessions/past/session")
    assert relocate_runtime_path(original) == root / "data/sessions/past/session"
    assert original == str(home / "axm/sessions/past/session")
    assert (
        relocate_runtime_path(home / ".axm/profiles/dev/session")
        == root / "profiles/dev/session"
    )
    assert profile_env()["AXM_ROOT"] == str(root)
