"""Strict diagnostics distinguish missing inputs from unsafe fallback success."""

from __future__ import annotations

import traceback
from pathlib import Path

import pytest

from axm_config import ConfigError, NamespaceStore, get, resolution_origin
from axm_config.cli import app
from axm_config.doctor import config_doctor_data
from axm_config.tools import ConfigDoctorTool


@pytest.fixture
def installation(tmp_path, monkeypatch):
    root = tmp_path / "installation"
    monkeypatch.setenv("AXM_ROOT", str(root))
    monkeypatch.setenv("AXM_PROFILE", "production")
    monkeypatch.delenv("AXM_HOME", raising=False)
    return root


def test_missing_configuration_is_normal_and_read_only(installation):
    assert config_doctor_data() == {}
    assert config_doctor_data("demo") == {}
    assert NamespaceStore(strict_reads=True).read("demo") == {}
    assert not installation.exists()


@pytest.mark.parametrize("source", ["central", "legacy", "home", "profile"])
def test_malformed_selected_sources_are_diagnosed_without_contents(
    installation,
    tmp_path,
    monkeypatch,
    source,
):
    installation.mkdir()
    path = installation / "config.toml"
    if source == "legacy":
        path = installation / "demo.toml"
    elif source == "home":
        home = tmp_path / "compatibility"
        home.mkdir()
        monkeypatch.setenv("AXM_HOME", str(home))
        path = home / "config.toml"
    elif source == "profile":
        monkeypatch.setenv("AXM_PROFILE", "dev")
        path = installation / "profiles/dev/config.toml"
        path.parent.mkdir(parents=True)
    path.write_text('token = "private-value-unclosed')
    before = path.stat()
    for namespace in ("demo", None):
        with pytest.raises(ConfigError, match="malformed TOML") as error:
            config_doctor_data(namespace)
        rendered = "".join(traceback.format_exception(error.value))
        assert "private-value" not in rendered
        assert "TOMLDecodeError" not in rendered
    assert path.stat().st_mtime_ns == before.st_mtime_ns
    assert path.stat().st_mode == before.st_mode


def test_shadowed_legacy_other_profile_and_foreign_toml_are_not_consulted(
    installation,
):
    installation.mkdir()
    (installation / "config.toml").write_text('[demo]\nkey = "central"\n')
    (installation / "demo.toml").write_text('broken = "private-value')
    (installation / "foreign-backup.toml").write_text('broken = "private-value')
    other = installation / "profiles/other"
    other.mkdir(parents=True)
    (other / "config.toml").write_text('broken = "private-value')
    assert config_doctor_data() == {"demo.key": {"layer": "file", "present": True}}


def test_unreadable_source_errors_never_render_oserror_payload(
    installation,
    monkeypatch,
):
    installation.mkdir()
    target = installation / "config.toml"
    target.write_text('[demo]\nkey = "private-value"\n')
    original = Path.open

    def guarded_open(path, *args, **kwargs):
        if path == target:
            raise PermissionError("private-value in operating system error")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    with pytest.raises(ConfigError, match="unreadable central") as error:
        config_doctor_data("demo")
    assert "private-value" not in "".join(traceback.format_exception(error.value))


def test_tolerant_runtime_reads_remain_compatible_but_strict_origin_refuses(
    installation,
    monkeypatch,
):
    installation.mkdir()
    (installation / "config.toml").write_text('broken = "private-value')
    assert get("demo", "key", default="fallback") == "fallback"
    monkeypatch.setenv("AXM_DEMO_KEY", "env-value")
    assert resolution_origin("demo", "key") == {"layer": "env", "present": True}
    with pytest.raises(ConfigError, match="malformed TOML"):
        resolution_origin("demo", "key", strict=True)
    with pytest.raises(ConfigError, match="malformed TOML"):
        config_doctor_data("demo")


def test_cli_and_tool_fail_without_partial_report_or_values(
    installation,
    capsys,
):
    installation.mkdir()
    (installation / "config.toml").write_text('broken = "private-value')
    with pytest.raises(SystemExit) as exit_info:
        app(["doctor", "demo"], result_action="return_none")
    assert exit_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "malformed TOML" in captured.err
    assert "private-value" not in captured.err
    result = ConfigDoctorTool().execute(namespace="demo")
    assert not result.success
    assert "malformed TOML" in result.error
    assert "private-value" not in str(result)


def test_strict_namespace_discovery_reports_unlistable_directory(
    installation,
    monkeypatch,
):
    import os

    installation.mkdir()
    (installation / "config.toml").write_text('[demo]\nkey="value"\n')
    original = os.scandir

    def guarded_scandir(path):
        if Path(path) == installation:
            raise PermissionError("private-value directory error")
        return original(path)

    monkeypatch.setattr(os, "scandir", guarded_scandir)
    with pytest.raises(ConfigError, match="namespace directory") as error:
        config_doctor_data()
    assert "private-value" not in "".join(traceback.format_exception(error.value))
    assert NamespaceStore().read("demo") == {"key": "value"}


def test_non_utf8_configuration_is_a_safe_malformed_diagnostic(installation):
    installation.mkdir()
    (installation / "config.toml").write_bytes(b"\xffprivate-value")
    with pytest.raises(ConfigError, match=r"malformed TOML.*config\.toml") as error:
        config_doctor_data()
    assert "private-value" not in "".join(traceback.format_exception(error.value))
