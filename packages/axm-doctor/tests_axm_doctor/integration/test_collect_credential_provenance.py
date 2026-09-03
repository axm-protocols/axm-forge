"""Integration tests for the live axm-vault credential catalogue."""

from __future__ import annotations

import importlib
from pathlib import Path

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


@pytest.mark.integration
def test_raising_declaration_degrades_only_its_provenance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AC4: one raising declaration gets a cautious row without aborting peers."""
    from importlib.metadata import distributions

    module = tmp_path / "fixture_provenance.py"
    module.write_text(
        """
from types import SimpleNamespace


class RaisingEntry:
    kind = "auth_dependency"
    present = False

    @property
    def layer(self):
        raise RuntimeError("status probe failed")


def good():
    return {
        "fixture.token": SimpleNamespace(
            kind="token", layer="env", present=True
        )
    }


def bad():
    return {"fixture.session": RaisingEntry()}
""".lstrip(),
        encoding="utf-8",
    )
    dist_info = tmp_path / "fixture_provenance-1.0.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: fixture-provenance\nVersion: 1.0\n",
        encoding="utf-8",
    )
    (dist_info / "entry_points.txt").write_text(
        "[axm.credentials]\ngood = fixture_provenance:good\n"
        "bad = fixture_provenance:bad\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    endpoints = [
        endpoint
        for distribution in distributions(path=[str(tmp_path)])
        for endpoint in distribution.entry_points
        if endpoint.group == "axm.credentials"
    ]

    def probe() -> dict[str, object]:
        report: dict[str, object] = {}
        for endpoint in endpoints:
            report.update(endpoint.load()())
        return report

    credentials = importlib.import_module("axm_doctor.credentials")
    rows = credentials.collect_credential_provenance(probe=probe)
    by_coordinate = {row.coordinate: row for row in rows}

    assert by_coordinate["fixture.token"].kind == "token"
    assert by_coordinate["fixture.token"].present is True
    assert by_coordinate["fixture.session"].kind == "auth_dependency"
    assert by_coordinate["fixture.session"].present is False
