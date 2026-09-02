"""Integration witnesses for the hermetic credential harness."""

from __future__ import annotations

import importlib
from pathlib import Path

import keyring
import pytest

from axm_init.adapters.credentials import CredentialManager

_SENTINEL = "pypi-AgEIcHlwaS5vcmc-SENTINEL"
_MEMORY_BACKEND_NAME = "MemoryKeyring"


def _assert_memory_keyring_is_active() -> object:
    backend = keyring.get_keyring()
    assert type(backend).__name__ == _MEMORY_BACKEND_NAME
    return backend


@pytest.mark.integration
def test_active_keyring_is_the_in_memory_backend() -> None:
    """AC1: integration tests use the harness memory keyring backend."""
    backend = _assert_memory_keyring_is_active()
    isolation = importlib.import_module("tests_axm_init.integration._keyring_isolation")

    assert type(backend) is isolation.MemoryKeyring


@pytest.mark.integration
def test_home_is_an_empty_per_test_temporary_directory(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """AC2: HOME is isolated below pytest's base directory without .pypirc."""
    home = Path.home().resolve()
    base_temp = tmp_path_factory.getbasetemp().resolve()

    assert home != base_temp
    assert base_temp in home.parents
    assert not (home / ".pypirc").exists()


@pytest.mark.integration
def test_seeded_token_is_read_exactly(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: CredentialManager reads the exact token seeded by the fixture."""
    monkeypatch.delenv("PYPI_API_TOKEN", raising=False)
    _assert_memory_keyring_is_active()
    request.getfixturevalue("seeded_pypi_keyring")

    assert CredentialManager().get_pypi_token() == _SENTINEL
