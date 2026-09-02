"""Value-free credential provenance collected from axm-vault."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol

from axm_vault.doctor import doctor_data
from pydantic import BaseModel

__all__ = ["CredentialProvenance", "collect_credential_provenance"]


class CredentialProvenance(BaseModel, frozen=True):  # type: ignore[explicit-any]
    """The serving layer and presence of one credential coordinate."""

    coordinate: str
    layer: str
    present: bool


class ProvenanceEntry(Protocol):
    """Structural shape accepted from an injected provenance probe."""

    layer: str
    present: bool


type ProvenanceValue = ProvenanceEntry | Mapping[str, str | bool]
type ProvenanceProbe = Callable[[], Mapping[str, ProvenanceValue]]


def _entry_fields(entry: ProvenanceValue) -> tuple[str, bool]:
    if isinstance(entry, Mapping):
        layer = entry["layer"]
        present = entry["present"]
        if not isinstance(layer, str) or not isinstance(present, bool):
            msg = "credential provenance must contain a string layer and bool present"
            raise TypeError(msg)
        return layer, present
    return entry.layer, entry.present


def collect_credential_provenance(
    *, probe: ProvenanceProbe | None = None
) -> list[CredentialProvenance]:
    """Translate vault provenance into typed rows without carrying values."""
    provenance = doctor_data() if probe is None else probe()
    rows: list[CredentialProvenance] = []
    for coordinate, entry in provenance.items():
        layer, present = _entry_fields(entry)
        rows.append(
            CredentialProvenance(
                coordinate=coordinate,
                layer=layer,
                present=False if layer == "missing" else present,
            )
        )
    return rows
