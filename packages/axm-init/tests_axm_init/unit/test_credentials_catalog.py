"""Unit tests for the axm-init credential catalog."""

from __future__ import annotations

import importlib

from axm_vault import CredentialGroup, CredentialSpec, Sensitivity


def test_pypi_credentials_declares_secret_token() -> None:
    """AC1: the PyPI catalog spec is explicitly classified as secret."""
    catalog_module = importlib.import_module("axm_init.credentials_catalog")

    matches = [
        (group, spec)
        for group in catalog_module.pypi_credentials()
        for spec in group.specs
        if spec.env == "PYPI_API_TOKEN"
    ]

    assert matches
    group, spec = matches[0]
    assert isinstance(group, CredentialGroup)
    assert isinstance(spec, CredentialSpec)
    assert spec.sensitivity is Sensitivity.SECRET


def test_pypi_credentials_uses_literal_environment_name() -> None:
    """AC1: the environment coordinate is literal, not name-derived."""
    catalog_module = importlib.import_module("axm_init.credentials_catalog")

    group = catalog_module.pypi_credentials()[0]
    spec = next(spec for spec in group.specs if spec.name == "token")

    assert spec.env == "PYPI_API_TOKEN"
    assert spec.env != f"{group.id}_{spec.name}".upper()
