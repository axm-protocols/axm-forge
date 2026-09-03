"""Integration coverage for resilient catalog discovery through doctor_data."""

from __future__ import annotations

from importlib import invalidate_caches
from importlib.metadata import entry_points as metadata_entry_points
from pathlib import Path

import pytest

from axm_vault import catalog as catalog_module
from axm_vault import doctor as doctor_module
from axm_vault.catalog import load_catalog
from axm_vault.doctor import doctor_data
from axm_vault.store import KeyringStore


def _install_mixed_disk_contributions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ok_module = """from axm_vault.models import CredentialGroup, CredentialSpec

GROUP = CredentialGroup(
    id="survivor",
    package="axm-survivor",
    title="Survivor",
    specs=(CredentialSpec(
        name="token",
        env="AXM_VAULT_SURVIVOR_TOKEN",
        kind="token",
        required=False,
    ),),
)

def groups():
    return [GROUP]
"""
    tmp_path.joinpath("doctor_fake_ok.py").write_text(ok_module, encoding="utf-8")
    tmp_path.joinpath("doctor_fake_broken.py").write_text(
        "ALREADY_BUILT = object()\n", encoding="utf-8"
    )

    distributions = (
        ("doctor-ok-fixture", "doctor-ok = doctor_fake_ok:groups"),
        (
            "doctor-broken-fixture",
            "doctor-broken = doctor_fake_broken:ALREADY_BUILT",
        ),
    )
    for distribution_name, declaration in distributions:
        normalized_name = distribution_name.replace("-", "_")
        metadata = tmp_path / f"{normalized_name}-1.0.dist-info"
        metadata.mkdir()
        metadata.joinpath("METADATA").write_text(
            f"Metadata-Version: 2.1\nName: {distribution_name}\nVersion: 1.0\n",
            encoding="utf-8",
        )
        metadata.joinpath("entry_points.txt").write_text(
            f"[axm.credentials]\n{declaration}\n",
            encoding="utf-8",
        )

    monkeypatch.syspath_prepend(str(tmp_path))
    invalidate_caches()

    def fixture_entry_points(*, group: str) -> list[object]:
        return [
            endpoint
            for endpoint in metadata_entry_points(group=group)
            if endpoint.name in {"doctor-ok", "doctor-broken"}
        ]

    monkeypatch.setattr(catalog_module, "entry_points", fixture_entry_points)
    load_catalog.cache_clear()


@pytest.fixture(autouse=True)
def _clear_catalog_cache() -> None:
    load_catalog.cache_clear()


@pytest.mark.integration
def test_doctor_data_survives_malformed_catalog_contribution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC7: doctor inventory retains conforming keys beside a malformed provider."""
    _install_mixed_disk_contributions(tmp_path, monkeypatch)
    monkeypatch.setattr(
        doctor_module.Resolver,
        "keyring_available",
        lambda self: False,
    )

    provenance = doctor_data()

    expected_key = KeyringStore.username("survivor", "token", None)
    assert expected_key in provenance
