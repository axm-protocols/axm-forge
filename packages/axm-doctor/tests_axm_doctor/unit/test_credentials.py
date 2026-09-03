"""Unit tests for value-free credential provenance reporting."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Protocol


class _CredentialsModule(Protocol):
    def collect_credential_provenance(self, *, probe: object = ...) -> list[object]: ...


def _credentials() -> _CredentialsModule:
    return importlib.import_module("axm_doctor.credentials")


def test_collect_preserves_the_serving_layer_per_coordinate() -> None:
    """AC1: each coordinate reports its own effective serving layer."""
    provenance = {
        "gh.token": SimpleNamespace(kind="token", layer="env", present=True),
        "svc.key": SimpleNamespace(kind="token", layer="file", present=True),
    }

    rows = _credentials().collect_credential_provenance(probe=lambda: provenance)
    by_coordinate = {row.coordinate: row for row in rows}

    assert by_coordinate["gh.token"].layer == "env"
    assert by_coordinate["svc.key"].layer == "file"
    assert by_coordinate["gh.token"].layer != by_coordinate["svc.key"].layer


def test_collect_reports_missing_coordinate_as_absent() -> None:
    """AC2: a missing coordinate stays on the missing layer and is absent."""
    provenance = {
        "svc.key": SimpleNamespace(kind="token", layer="missing", present=False)
    }

    rows = _credentials().collect_credential_provenance(probe=lambda: provenance)

    assert len(rows) == 1
    assert rows[0].coordinate == "svc.key"
    assert rows[0].present is False
    assert rows[0].layer == "missing"


def test_collected_row_is_strictly_value_free() -> None:
    """AC3: serialized provenance exposes only coordinate, layer, and presence."""
    provenance = {
        "svc.key": SimpleNamespace(
            kind="token",
            layer="file",
            present=True,
            value="SENTINEL-SECRET-VALUE",
        )
    }

    row = _credentials().collect_credential_provenance(probe=lambda: provenance)[0]
    dumped = row.model_dump()

    assert set(dumped) == {"coordinate", "kind", "layer", "present"}
    assert "SENTINEL-SECRET-VALUE" not in repr(dumped)


def test_collect_preserves_declared_kind_per_entry() -> None:
    """AC1: provenance distinguishes a credential from an auth dependency."""
    from axm_doctor.credentials import ProvenanceEntry

    credential: ProvenanceEntry = SimpleNamespace(
        kind="token", layer="env", present=True
    )
    auth_dependency: ProvenanceEntry = SimpleNamespace(
        kind="auth_dependency", layer="disconnected", present=False
    )

    rows = _credentials().collect_credential_provenance(
        probe=lambda: {
            "service.token": credential,
            "github.session": auth_dependency,
        }
    )
    by_coordinate = {row.coordinate: row for row in rows}

    assert by_coordinate["service.token"].kind == "token"
    assert by_coordinate["github.session"].kind == "auth_dependency"
    assert by_coordinate["service.token"].kind != by_coordinate["github.session"].kind
