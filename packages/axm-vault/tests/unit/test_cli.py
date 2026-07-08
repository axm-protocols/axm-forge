"""Unit tests for axm_vault.cli — cyclopts command surface."""

from __future__ import annotations

import pytest

from axm_vault import cli
from axm_vault.catalog import Catalog
from axm_vault.cli import app
from axm_vault.models import CredentialGroup, CredentialSpec, Sensitivity

_EXPECTED = {"setup", "get", "set", "rotate", "doctor", "path"}


def _catalog_with(sensitivity: Sensitivity) -> Catalog:
    """A one-group catalog whose single ``svc.token`` spec has ``sensitivity``."""
    group = CredentialGroup(
        id="svc",
        package="pkg",
        title="Service",
        specs=(
            CredentialSpec(
                name="token", env="SVC_TOKEN", kind="token", sensitivity=sensitivity
            ),
        ),
    )
    return Catalog(groups=(group,))


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


@pytest.mark.parametrize("sensitivity", [Sensitivity.CONFIG, Sensitivity.NONSENSITIVE])
def test_rotate_rejects_non_secret_spec(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    sensitivity: Sensitivity,
) -> None:
    """``rotate`` on a non-SECRET spec exits 1 and never touches the keyring.

    Rotating a CONFIG/NONSENSITIVE spec would write an orphan into the keyring
    that ``get`` never reads (keyring is SECRET-only) — a silent no-op reported
    as success. The catalog check must turn it into an up-front error before
    ``rotate_secret`` runs.
    """
    monkeypatch.setattr(cli, "load_catalog", lambda: _catalog_with(sensitivity))

    def _fail_rotate(*_a: object, **_k: object) -> None:
        raise AssertionError("rotate_secret must not run for a non-SECRET spec")

    monkeypatch.setattr(cli, "rotate_secret", _fail_rotate)

    with pytest.raises(SystemExit) as excinfo:
        cli.rotate("svc", "token", "v2")

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert sensitivity.value.upper() in captured.err
    assert captured.out == ""


def test_rotate_unknown_name_exits_clean(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``rotate`` on an unknown spec name exits 1, never writing a keyring orphan."""
    monkeypatch.setattr(cli, "load_catalog", lambda: _catalog_with(Sensitivity.SECRET))

    def _fail_rotate(*_a: object, **_k: object) -> None:
        raise AssertionError("rotate_secret must not run for an unknown spec")

    monkeypatch.setattr(cli, "rotate_secret", _fail_rotate)

    with pytest.raises(SystemExit) as excinfo:
        cli.rotate("svc", "nope", "v2")

    assert excinfo.value.code == 1
    assert "nope" in capsys.readouterr().err


def test_rotate_secret_spec_calls_rotate(monkeypatch: pytest.MonkeyPatch) -> None:
    """``rotate`` on a SECRET spec resolves through the catalog then rotates."""
    monkeypatch.setattr(cli, "load_catalog", lambda: _catalog_with(Sensitivity.SECRET))
    calls: list[tuple[str, str, str, str | None]] = []
    monkeypatch.setattr(
        cli,
        "rotate_secret",
        lambda g, n, v, i=None: calls.append((g, n, v, i)),
    )

    cli.rotate("svc", "token", "v2")

    assert calls == [("svc", "token", "v2", None)]
