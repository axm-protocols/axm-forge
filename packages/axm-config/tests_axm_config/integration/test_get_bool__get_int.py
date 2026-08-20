"""Integration coverage for typed configuration helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

import axm_config
from axm_config import get_path

pytestmark = pytest.mark.integration


def _configure_empty_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    config_home = tmp_path / "axm-home"
    config_home.mkdir()
    monkeypatch.setenv("AXM_HOME", str(config_home))
    return config_home


def test_get_path_routes_environment_value_to_warden_namespace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1: the requested namespace selects AXM_WARDEN_BINARY_PATH."""
    _configure_empty_home(tmp_path, monkeypatch)
    monkeypatch.setenv("AXM_WARDEN_BINARY_PATH", "~/tools/axm-warden")
    default = Path("/d")

    result = get_path("binary_path", default=default, namespace="warden")

    assert result.is_absolute()
    assert result != default
    assert result.parts[-2:] == ("tools", "axm-warden")


def test_get_path_routes_file_value_to_warden_namespace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1: the requested namespace reads binary_path from [warden]."""
    config_home = _configure_empty_home(tmp_path, monkeypatch)
    (config_home / "config.toml").write_text(
        '[warden]\nbinary_path = "~/tools/axm-warden"\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("AXM_WARDEN_BINARY_PATH", raising=False)

    result = get_path("binary_path", default=Path("/d"), namespace="warden")

    assert result.is_absolute()
    assert result.parts[-2:] == ("tools", "axm-warden")


def test_get_int_preserves_toml_integer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: a parsed integer from the [warden] table remains an integer."""
    config_home = _configure_empty_home(tmp_path, monkeypatch)
    (config_home / "config.toml").write_text(
        "[warden]\nmax_concurrent = 4\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("AXM_WARDEN_MAX_CONCURRENT", raising=False)

    result = axm_config.get_int("max_concurrent", 0, namespace="warden")

    assert result == 4
    assert isinstance(result, int)


def test_get_bool_preserves_toml_boolean(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: a parsed boolean from the [warden] table remains unchanged."""
    config_home = _configure_empty_home(tmp_path, monkeypatch)
    (config_home / "config.toml").write_text(
        "[warden]\nautostart = false\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("AXM_WARDEN_AUTOSTART", raising=False)

    assert axm_config.get_bool("autostart", True, namespace="warden") is False


def test_environment_integer_outranks_file_and_is_coerced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: an environment integer wins over TOML and is still coerced."""
    config_home = _configure_empty_home(tmp_path, monkeypatch)
    (config_home / "config.toml").write_text(
        "[warden]\nmax_concurrent = 2\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AXM_WARDEN_MAX_CONCURRENT", "8")

    result = axm_config.get_int("max_concurrent", 0, namespace="warden")

    assert result == 8
    assert isinstance(result, int)


def test_all_helpers_return_defaults_verbatim_without_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: a missing file and environment leave every default untouched."""
    _configure_empty_home(tmp_path, monkeypatch)
    for variable in (
        "AXM_WARDEN_LOG_PATH",
        "AXM_WARDEN_MAX_CONCURRENT",
        "AXM_WARDEN_AUTOSTART",
        "AXM_WARDEN_MODE",
    ):
        monkeypatch.delenv(variable, raising=False)
    path_default = Path("~/raw/wardenlog")
    int_default = 4
    bool_default = True
    str_default = "embedded"

    assert (
        get_path("log_path", default=path_default, namespace="warden") == path_default
    )
    assert (
        axm_config.get_int("max_concurrent", int_default, namespace="warden")
        is int_default
    )
    assert (
        axm_config.get_bool("autostart", bool_default, namespace="warden")
        is bool_default
    )
    assert axm_config.get_str("mode", str_default, namespace="warden") is str_default
