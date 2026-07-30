"""Unit tests for the axm-config cyclopts CLI.

These tests exercise the command-delegation wiring without real I/O: the
central functions are mocked so we only verify the CLI parses arguments and
delegates to the requete->reponse layer (AXMTool-first; no logic in the CLI).
"""

from __future__ import annotations

import pytest

from axm_config.cli import app


def test_get_command_delegates(mocker: pytest.MonkeyPatch) -> None:
    """AC5: ``get`` command body delegates to the central ``get`` function."""
    spy = mocker.patch("axm_config.cli.get", return_value="resolved-value")

    app(["get", "demo", "key"], result_action="return_none")

    spy.assert_called_once_with("demo", "key")


def test_set_command_delegates(mocker: pytest.MonkeyPatch) -> None:
    """AC5: ``set`` command body delegates to the central ``set_`` function."""
    spy = mocker.patch("axm_config.cli.set_")

    app(["set", "demo", "key", "value"], result_action="return_none")

    spy.assert_called_once_with("demo", "key", "value")


def test_path_command_delegates(mocker: pytest.MonkeyPatch) -> None:
    """AC5: ``path`` command body delegates to the central ``axm_home``."""
    spy = mocker.patch("axm_config.cli.axm_home")

    app(["path"], result_action="return_none")

    spy.assert_called_once_with()


def test_doctor_command_delegates(mocker: pytest.MonkeyPatch) -> None:
    """AC5: ``doctor`` command body delegates to ``config_doctor_data``."""
    spy = mocker.patch(
        "axm_config.cli.config_doctor_data",
        return_value={"demo.key": {"layer": "file", "present": True}},
    )

    app(["doctor", "demo"], result_action="return_none")

    spy.assert_called_once_with("demo")


def test_get_oserror_exits_clean(
    mocker: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unwritable ``~/.axm`` surfaces as stderr + exit 1, not a traceback."""
    mocker.patch(
        "axm_config.cli.get",
        side_effect=PermissionError(13, "Permission denied"),
    )

    with pytest.raises(SystemExit) as excinfo:
        app(["get", "demo", "key"], result_action="return_none")

    assert excinfo.value.code == 1
    assert "error:" in capsys.readouterr().err


def test_set_oserror_exits_clean(
    mocker: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A failed write surfaces as a clean stderr message + exit 1."""
    mocker.patch(
        "axm_config.cli.set_",
        side_effect=PermissionError(13, "Permission denied"),
    )

    with pytest.raises(SystemExit) as excinfo:
        app(["set", "demo", "key", "value"], result_action="return_none")

    assert excinfo.value.code == 1
    assert "error:" in capsys.readouterr().err


def test_path_oserror_exits_clean(
    mocker: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``path`` failing to create ``~/.axm`` exits 1 with a stderr message."""
    mocker.patch(
        "axm_config.cli.axm_home",
        side_effect=PermissionError(13, "Permission denied"),
    )

    with pytest.raises(SystemExit) as excinfo:
        app(["path"], result_action="return_none")

    assert excinfo.value.code == 1
    assert "error:" in capsys.readouterr().err


def test_doctor_oserror_exits_clean(
    mocker: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``doctor`` failing to enumerate namespaces exits 1 with stderr."""
    mocker.patch(
        "axm_config.cli.config_doctor_data",
        side_effect=PermissionError(13, "Permission denied"),
    )

    with pytest.raises(SystemExit) as excinfo:
        app(["doctor"], result_action="return_none")

    assert excinfo.value.code == 1
    assert "error:" in capsys.readouterr().err
