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


def test_relocation_is_idempotent_for_canonical_runtime(tmp_path, monkeypatch):
    root = tmp_path / "axm"
    monkeypatch.setenv("AXM_ROOT", str(root))
    for relative in (
        "data/sessions/g/run",
        "state/orison",
        "profiles/dev",
        "config.toml",
    ):
        canonical = root / relative
        assert relocate_runtime_path(canonical) == canonical
        assert relocate_runtime_path(relocate_runtime_path(canonical)) == canonical
    assert not root.exists()


def test_path_command_is_read_only_and_init_is_explicit(tmp_path, monkeypatch, capsys):
    from axm_config.cli import app

    root = tmp_path / "installation"
    monkeypatch.setenv("AXM_ROOT", str(root))
    app(["path"], result_action="return_none")
    assert not root.exists()
    app(["init"], result_action="return_none")
    assert root.is_dir()
    assert list(root.iterdir()) == []


def test_origin_matches_fallback_without_exposing_value(tmp_path, monkeypatch):
    from axm_config.resolver import resolution_origin, resolve

    root = tmp_path / "installation"
    override = tmp_path / "override"
    override.mkdir()
    (override / "config.toml").write_text('[demo.child]\ntoken="private-value"\n')
    monkeypatch.setenv("AXM_ROOT", str(root))
    monkeypatch.setenv("AXM_HOME", str(override))
    assert resolve("demo.child", "token") == "private-value"
    assert resolution_origin("demo.child", "token") == {
        "layer": "home",
        "present": True,
    }
    monkeypatch.setenv("AXM_DEMO__CHILD_TOKEN", "env-private-value")
    report = resolution_origin("demo.child", "token")
    assert report == {"layer": "env", "present": True}
    assert "private-value" not in str(report)
    assert not root.exists()


def test_case_alias_of_existing_root_does_not_duplicate_data(tmp_path, monkeypatch):
    root = tmp_path / "AXM"
    root.mkdir()
    alias = tmp_path / "axm"
    if not alias.exists():
        pytest.skip("case-sensitive volume")
    monkeypatch.setenv("AXM_ROOT", str(root))
    path = alias / "data/sessions/g/run"
    assert relocate_runtime_path(path) == root / "data/sessions/g/run"


def test_doctor_enumerates_home_only_nested_namespace_and_alias_origin(
    tmp_path, monkeypatch
):
    from axm_config.doctor import config_doctor_data
    from axm_config.resolver import resolution_origin, resolve

    root = tmp_path / "installation"
    home = tmp_path / "override"
    home.mkdir()
    (home / "config.toml").write_text('[demo.child]\ntoken="private-value"\n')
    monkeypatch.setenv("AXM_ROOT", str(root))
    monkeypatch.setenv("AXM_HOME", str(home))
    assert config_doctor_data("demo.child")["demo.child.token"] == {
        "layer": "home",
        "present": True,
    }
    assert config_doctor_data()["demo.child.token"]["layer"] == "home"
    monkeypatch.setenv("AXM_LEGACY_TOKEN", "alias-private-value")
    aliases = ("AXM_LEGACY_TOKEN",)
    assert resolve("demo.child", "token", env_aliases=aliases) == "alias-private-value"
    assert resolution_origin("demo.child", "token", env_aliases=aliases) == {
        "layer": "env",
        "present": True,
    }
    monkeypatch.setenv("AXM_DEMO__CHILD_TOKEN", "canonical-value")
    assert resolve("demo.child", "token", env_aliases=aliases) == "canonical-value"
    root.mkdir()
    (root / "config.toml").write_text('[demo.child]\ntoken="installation-value"\n')
    monkeypatch.delenv("AXM_DEMO__CHILD_TOKEN")
    monkeypatch.delenv("AXM_LEGACY_TOKEN")
    assert resolve("demo.child", "token") == "installation-value"
    assert resolution_origin("demo.child", "token")["layer"] == "file"


@pytest.mark.parametrize("suffix", ["../outside", "/tmp/outside"])
@pytest.mark.parametrize("helper", ["state", "data"])
def test_runtime_suffixes_cannot_escape_root(tmp_path, monkeypatch, suffix, helper):
    from axm_config.home import axm_data_path

    root = tmp_path / "installation"
    monkeypatch.setenv("AXM_ROOT", str(root))
    getter = axm_state_path if helper == "state" else axm_data_path
    with pytest.raises(ValueError, match="relative"):
        getter(suffix)
    assert not root.exists()


def test_runtime_data_symlink_cannot_escape_installation(tmp_path, monkeypatch):
    from axm_config.home import axm_data_path

    root = tmp_path / "installation"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "data").symlink_to(outside, target_is_directory=True)
    monkeypatch.setenv("AXM_ROOT", str(root))
    with pytest.raises(ValueError, match="installation"):
        axm_data_path("sessions")
    assert list(outside.iterdir()) == []
