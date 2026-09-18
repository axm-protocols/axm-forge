"""Integration witnesses for the caller-supplied credential capability.

Every row crosses a real boundary: a stub catalog installed at BOTH resolution
seams (``axm_doctor.orchestrate`` for the census, ``axm_vault.tools`` for the
delegated write) plus a real keyring or config store redirected under
``tmp_path``. The outcome asserted in each test is decided by
``provide_secret``'s own re-resolution of the catalog, never by a stubbed
return value.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import keyring
import pytest
from axm_vault.catalog import Catalog
from axm_vault.models import CredentialGroup, CredentialSpec, Sensitivity
from axm_vault.store import KeyringStore
from keyring.backend import KeyringBackend
from keyring.errors import PasswordDeleteError
from pytest import LogCaptureFixture, MonkeyPatch

from axm_doctor import orchestrate

#: A dot-free group id: ``KeyringStore.username`` and the ``{group}.{name}``
#: coordinate used by ``ProvisionResult.still_missing`` then coincide, so the
#: assertions bind to the coordinate itself rather than to one spelling of it.
_GROUP = "fixture"
_NAME = "token"
_ENV = "FIXTURE_PROVIDE_TOKEN"
_COORDINATE = f"{_GROUP}.{_NAME}"
_OTHER_ENV = "FIXTURE_PROVIDE_OTHER"
_CONFIG_GROUP = "fixtureconfig"
_CONFIG_ENV = "FIXTURE_PROVIDE_CONFIG"
_PLAIN_GROUP = "fixtureplain"
_PLAIN_ENV = "FIXTURE_PROVIDE_PLAIN"

#: A distinctive 32-character value whose head and tail are searched for too.
_VALUE = "qxv7k2m9zt4bw8ns6hd1jr5pl3gc0yfa"


class _DiscardingKeyring(KeyringBackend):
    """A backend that accepts every write and hands nothing back."""

    priority = 1.0

    def __init__(self) -> None:
        super().__init__()  # type: ignore[no-untyped-call] # keyring lacks stubs

    def get_password(self, service: str, username: str) -> str | None:
        return None

    def set_password(self, service: str, username: str, password: str) -> None:
        return None

    def delete_password(self, service: str, username: str) -> None:
        raise PasswordDeleteError("not found")


@pytest.fixture
def discarding_keyring() -> Iterator[_DiscardingKeyring]:
    """Install a keyring backend that persists nothing, restoring the prior one."""
    previous = keyring.get_keyring()
    backend = _DiscardingKeyring()
    keyring.set_keyring(backend)
    try:
        yield backend
    finally:
        keyring.set_keyring(previous)


def _spec(name: str, env: str, sensitivity: Sensitivity) -> CredentialSpec:
    """Build one catalog spec carrying the sensitivity under test."""
    return CredentialSpec(name=name, env=env, kind="token", sensitivity=sensitivity)


def _catalog(group: str, specs: tuple[CredentialSpec, ...]) -> Catalog:
    """Wrap ``specs`` into a one-group fixture catalog."""
    return Catalog(
        groups=(
            CredentialGroup(
                id=group,
                package="axm-fixture",
                title="Provide",
                specs=specs,
            ),
        )
    )


def _install(monkeypatch: MonkeyPatch, catalog: Catalog) -> None:
    """Install the stub catalog at both the census and the write seam."""
    monkeypatch.setattr("axm_doctor.orchestrate.load_catalog", lambda: catalog)
    monkeypatch.setattr("axm_vault.tools.load_catalog", lambda: catalog)


@pytest.mark.integration
def test_provide_secret_stores_a_secret_without_a_terminal(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    memory_keyring: object,
) -> None:
    """AC1: a caller-supplied SECRET is stored while stdin is not a terminal."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv(_ENV, raising=False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    _install(monkeypatch, _catalog(_GROUP, (_spec(_NAME, _ENV, Sensitivity.SECRET),)))

    result = orchestrate.provide_secret(group=_GROUP, name=_NAME, value=_VALUE)

    assert result.stored is True
    assert result.target is not None
    assert result.target.startswith("keyring:")


@pytest.mark.integration
def test_provide_secret_attests_through_catalog_re_resolution(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    memory_keyring: object,
) -> None:
    """AC2: the census loses only the supplied coordinate, and still_missing agrees."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv(_ENV, raising=False)
    monkeypatch.delenv(_OTHER_ENV, raising=False)
    _install(
        monkeypatch,
        _catalog(
            _GROUP,
            (
                _spec(_NAME, _ENV, Sensitivity.SECRET),
                _spec("other", _OTHER_ENV, Sensitivity.SECRET),
            ),
        ),
    )
    before = [f"{item.group}.{item.name}" for item in orchestrate.missing_secrets()]

    result = orchestrate.provide_secret(group=_GROUP, name=_NAME, value=_VALUE)

    after = [f"{item.group}.{item.name}" for item in orchestrate.missing_secrets()]
    remaining = [coord for coord in before if coord != _COORDINATE]
    assert _COORDINATE in before
    assert remaining == [f"{_GROUP}.other"]
    assert after == remaining
    assert result.still_missing == remaining


@pytest.mark.integration
def test_provide_secret_reports_a_write_that_persisted_nothing(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    discarding_keyring: object,
) -> None:
    """AC3: a delegated write that stored nothing is reported as a failure."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv(_ENV, raising=False)
    _install(monkeypatch, _catalog(_GROUP, (_spec(_NAME, _ENV, Sensitivity.SECRET),)))

    result = orchestrate.provide_secret(group=_GROUP, name=_NAME, value=_VALUE)

    assert result.stored is False
    assert _COORDINATE in result.still_missing
    assert result.reason
    assert _COORDINATE in result.reason


@pytest.mark.integration
def test_provide_secret_stores_a_config_credential(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    memory_keyring: object,
) -> None:
    """AC4: a CONFIG credential is stored and attested on the same footing."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv(_CONFIG_ENV, raising=False)
    _install(
        monkeypatch,
        _catalog(_CONFIG_GROUP, (_spec(_NAME, _CONFIG_ENV, Sensitivity.CONFIG),)),
    )

    result = orchestrate.provide_secret(group=_CONFIG_GROUP, name=_NAME, value=_VALUE)

    assert result.stored is True
    assert result.target is not None
    assert result.target.startswith("config:")
    assert (_CONFIG_GROUP, _NAME) not in {
        (item.group, item.name) for item in orchestrate.missing_secrets()
    }


@pytest.mark.integration
def test_provide_secret_refuses_a_nonsensitive_credential(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    memory_keyring: object,
) -> None:
    """AC5: a NONSENSITIVE credential is refused by name and never stored."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv(_PLAIN_ENV, raising=False)
    _install(
        monkeypatch,
        _catalog(_PLAIN_GROUP, (_spec(_NAME, _PLAIN_ENV, Sensitivity.NONSENSITIVE),)),
    )

    result = orchestrate.provide_secret(group=_PLAIN_GROUP, name=_NAME, value=_VALUE)

    assert result.stored is False
    assert result.reason is not None
    assert "nonsensitive" in result.reason.lower()
    assert KeyringStore().get(_PLAIN_GROUP, _NAME) is None


@pytest.mark.integration
def test_provide_secret_never_leaks_the_supplied_value(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    memory_keyring: object,
    caplog: LogCaptureFixture,
) -> None:
    """AC6: neither the value nor its head or tail reaches the result or the logs."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv(_ENV, raising=False)
    _install(monkeypatch, _catalog(_GROUP, (_spec(_NAME, _ENV, Sensitivity.SECRET),)))

    with caplog.at_level(logging.DEBUG):
        result = orchestrate.provide_secret(group=_GROUP, name=_NAME, value=_VALUE)

    assert result.stored is True
    rendered = result.model_dump_json()
    logged = "\n".join(record.getMessage() for record in caplog.records)
    for fragment in (_VALUE, _VALUE[:8], _VALUE[-8:]):
        assert fragment not in rendered
        assert fragment not in logged
