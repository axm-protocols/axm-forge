"""Integration tests for the live axm-vault credential catalogue."""

from __future__ import annotations

import importlib

import pytest
from axm_vault.doctor import doctor_data


@pytest.mark.integration
def test_default_probe_matches_the_live_vault_catalogue() -> None:
    """AC4: the default probe returns exactly the live vault coordinates."""
    credentials = importlib.import_module("axm_doctor.credentials")

    rows = credentials.collect_credential_provenance()
    live_provenance = doctor_data()

    assert {row.coordinate for row in rows} == set(live_provenance)
    if not live_provenance:
        assert rows == []
