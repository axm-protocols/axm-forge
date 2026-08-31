"""Integration coverage for axm-init credentials discovered by doctor."""

from __future__ import annotations

import importlib

import keyring
import pytest
from axm_doctor.orchestrate import missing_secrets
from keyring.backend import KeyringBackend


class _EmptyKeyring(KeyringBackend):
    priority = 1

    def __init__(self) -> None:
        pass

    def get_password(self, service: str, username: str) -> str | None:
        return None

    def set_password(self, service: str, username: str, password: str) -> None:
        raise AssertionError("empty keyring must not be written")

    def delete_password(self, service: str, username: str) -> None:
        return None


@pytest.mark.integration
def test_missing_secrets_includes_pypi_environment_coordinate(
    tmp_path: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: doctor inventories the missing PYPI_API_TOKEN credential."""
    monkeypatch.delenv("PYPI_API_TOKEN", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    catalog_module = importlib.import_module("axm_init.credentials_catalog")
    groups = catalog_module.pypi_credentials()
    previous_backend = keyring.get_keyring()
    keyring.set_keyring(_EmptyKeyring())
    try:
        missing = missing_secrets()
    finally:
        keyring.set_keyring(previous_backend)

    assert any(
        spec.env == "PYPI_API_TOKEN"
        for entry in missing
        for group in groups
        if entry.group == group.id
        for spec in group.specs
        if entry.name == spec.name
    )
