"""Unit tests for axm_vault.cli — cyclopts command surface."""

from __future__ import annotations

import pytest

from axm_vault import cli
from axm_vault.catalog import Catalog
from axm_vault.cli import app

_EXPECTED = {"setup", "get", "set", "rotate", "doctor", "path"}


def _command_names() -> set[str]:
    """Collect the user-facing command names registered on the cyclopts app."""
    names: set[str] = set()
    for key in app:
        if key.startswith("--"):
            continue
        names.add(key)
    return names


def test_cli_has_no_import_command() -> None:
    """AC4: CLI exposes setup/get/set/rotate/doctor/path and NO 'import'."""
    names = _command_names()
    assert "import" not in names
    assert _EXPECTED <= names


def test_get_unknown_group_exits_clean(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``get`` on an unknown group exits 1 with stderr, not a raw traceback."""
    monkeypatch.setattr(cli, "load_catalog", Catalog)

    with pytest.raises(SystemExit) as excinfo:
        cli.get("nope", "key")

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "nope" in captured.err
    assert captured.out == ""
