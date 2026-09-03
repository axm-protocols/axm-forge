"""Value-free credential provenance collected from axm-vault."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol

from axm_vault import load_catalog
from axm_vault.catalog import Catalog
from axm_vault.doctor import doctor_data
from axm_vault.store import KeyringStore
from pydantic import BaseModel

__all__ = ["CredentialProvenance", "collect_credential_provenance"]


class CredentialProvenance(BaseModel, frozen=True):  # type: ignore[explicit-any]
    """The serving layer and presence of one credential coordinate."""

    coordinate: str
    kind: str = "credential"
    layer: str
    present: bool


class ProvenanceEntry(Protocol):
    """Structural shape accepted from an injected provenance probe."""

    kind: str
    layer: str
    present: bool


type ProvenanceValue = ProvenanceEntry | Mapping[str, str | bool]
type ProvenanceProbe = Callable[[], Mapping[str, ProvenanceValue]]


def _entry_kind(entry: ProvenanceValue) -> str:
    kind = (
        entry.get("kind", "credential")
        if isinstance(entry, Mapping)
        else getattr(entry, "kind", "credential")
    )
    if not isinstance(kind, str):
        msg = "credential provenance kind must be a string"
        raise TypeError(msg)
    return kind


def _catalog_kinds(catalog: Catalog) -> dict[str, str]:
    kinds: dict[str, str] = {}
    for group in catalog.groups():
        if group.multi and group.instances is not None:
            declared_instances = tuple(group.instances.list_instances())
            instances: tuple[str | None, ...] = declared_instances or (None,)
        else:
            instances = (None,)
        for spec in group.specs:
            for instance in instances:
                coordinate = KeyringStore.username(group.id, spec.name, instance)
                kinds[coordinate] = spec.kind
    return kinds


def _auth_dependency_rows(catalog: Catalog) -> list[CredentialProvenance]:
    rows: list[CredentialProvenance] = []
    for group in catalog.groups():
        for dependency in group.auth_dependencies:
            try:
                layer = str(dependency.status())
                present = layer == "connected"
            except Exception:  # noqa: BLE001 # one declaration must not abort the report
                layer = "unknown"
                present = False
            rows.append(
                CredentialProvenance(
                    coordinate=f"{group.id}.{dependency.name}",
                    kind="auth_dependency",
                    layer=layer,
                    present=present,
                )
            )
    return rows


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
    catalog: Catalog | None = None
    provenance: Mapping[str, ProvenanceValue]
    declared_kinds: dict[str, str] = {}
    if probe is None:
        catalog = load_catalog()
        provenance = doctor_data(catalog=catalog)
        declared_kinds = _catalog_kinds(catalog)
    else:
        provenance = probe()
    rows: list[CredentialProvenance] = []
    for coordinate, entry in provenance.items():
        kind = declared_kinds.get(coordinate, "unknown")
        try:
            if kind == "unknown":
                kind = _entry_kind(entry)
            layer, present = _entry_fields(entry)
        except Exception:  # noqa: BLE001 # isolate one malformed declaration
            layer = "unknown"
            present = False
        rows.append(
            CredentialProvenance(
                coordinate=coordinate,
                kind=kind,
                layer=layer,
                present=False if layer == "missing" else present,
            )
        )
    if catalog is not None:
        rows.extend(_auth_dependency_rows(catalog))
    return rows
