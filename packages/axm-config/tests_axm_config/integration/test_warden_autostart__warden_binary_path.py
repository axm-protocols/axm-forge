"""Integration coverage for the public warden configuration getters."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import axm_config
from axm_config import ConfigError

_WARDEN_ENV_KEYS = (
    "AUTOSTART",
    "BINARY_PATH",
    "LOG_PATH",
    "MAX_CONCURRENT",
    "MODE",
)


def _point_axm_home(
    home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("AXM_HOME", str(home / ".axm"))
    for key in _WARDEN_ENV_KEYS:
        monkeypatch.delenv(f"AXM_WARDEN_{key}", raising=False)
    return home / ".axm"


def _write_config(axm_dir: Path, warden_table: str) -> None:
    axm_dir.mkdir(parents=True, exist_ok=True)
    (axm_dir / "config.toml").write_text(
        f"[warden]\n{warden_table}",
        encoding="utf-8",
    )


@pytest.mark.integration
def test_environment_binary_path_is_expanded_and_absolute(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3, AC5: a configured environment path passes through resolve_safe."""
    _point_axm_home(tmp_path, monkeypatch)
    monkeypatch.setenv("AXM_WARDEN_BINARY_PATH", "~/bin/axm-warden")

    result = axm_config.warden_binary_path()

    assert isinstance(result, Path)
    assert result.is_absolute()
    assert result == (tmp_path / "bin" / "axm-warden").resolve()


@pytest.mark.integration
def test_unconfigured_getters_return_their_derived_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1: absent environment and config preserve every canonical default."""
    expected_axm_home = _point_axm_home(tmp_path, monkeypatch)

    assert axm_config.warden_mode() == "embedded"
    assert axm_config.warden_max_concurrent() == 4
    assert axm_config.warden_autostart() is True
    assert axm_config.warden_binary_path() == Path(sys.executable).parent / "axm-warden"
    assert axm_config.warden_log_path() == expected_axm_home / "warden.log"
    assert axm_config.axm_home() == expected_axm_home.resolve()


@pytest.mark.integration
def test_log_path_default_is_recomputed_after_home_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: the derived log default follows the AXM home on every call."""
    first_home = tmp_path / "first"
    second_home = tmp_path / "second"

    first_axm_home = _point_axm_home(first_home, monkeypatch)
    first_result = axm_config.warden_log_path()
    second_axm_home = _point_axm_home(second_home, monkeypatch)
    second_result = axm_config.warden_log_path()

    assert first_result == first_axm_home.resolve() / "warden.log"
    assert second_result == second_axm_home.resolve() / "warden.log"
    assert first_result != second_result


@pytest.mark.integration
def test_warden_table_drives_every_getter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3, AC5: typed file values and resolved paths drive all getters."""
    axm_dir = _point_axm_home(tmp_path, monkeypatch)
    _write_config(
        axm_dir,
        (
            'mode = "pull"\n'
            "max_concurrent = 8\n"
            "autostart = false\n"
            'binary_path = "~/bin/axm-warden"\n'
            'log_path = "~/logs/warden.log"\n'
        ),
    )

    assert axm_config.warden_mode() == "pull"
    assert axm_config.warden_max_concurrent() == 8
    assert axm_config.warden_autostart() is False
    assert (
        axm_config.warden_binary_path() == (tmp_path / "bin" / "axm-warden").resolve()
    )
    assert axm_config.warden_log_path() == (tmp_path / "logs" / "warden.log").resolve()


@pytest.mark.integration
def test_environment_overrides_file_and_remains_typed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: environment precedence still returns the declared integer type."""
    axm_dir = _point_axm_home(tmp_path, monkeypatch)
    _write_config(axm_dir, "max_concurrent = 8\n")
    monkeypatch.setenv("AXM_WARDEN_MAX_CONCURRENT", "2")

    result = axm_config.warden_max_concurrent()

    assert result == 2
    assert isinstance(result, int)


@pytest.mark.integration
def test_invalid_mode_in_warden_table_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: an unsupported mode from the real file layer raises ConfigError."""
    axm_dir = _point_axm_home(tmp_path, monkeypatch)
    _write_config(axm_dir, 'mode = "daemon"\n')

    with pytest.raises(ConfigError):
        axm_config.warden_mode()


@pytest.mark.integration
def test_explicit_log_default_is_returned_untouched(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC5: an explicit default is neither expanded nor validated."""
    _point_axm_home(tmp_path, monkeypatch)
    default = Path("~/raw/wardenlog")

    assert axm_config.warden_log_path(default=default) == default
