"""Shared unit declarations, resolved before any scaffold mutation."""

from __future__ import annotations

import tomllib
from typing import cast

from tomlkit import aot, dumps, parse, table
from tomlkit.items import AoT

from axm_init.core.toml_edit import table_at
from axm_init.models.protocol_scaffold import ProtocolScaffoldDecl, ProtocolUnitDecl

__all__ = ["merge_protocol_unit", "resolve_protocol_unit"]


def _units(metadata: str) -> tuple[str, list[dict[str, object]]]:
    data = cast("dict[str, object]", tomllib.loads(metadata))
    current: object = data
    for key in ("tool", "axm-init", "protocols"):
        if not isinstance(current, dict):
            raise ValueError("protocol profile must be a table")
        current = current.get(key, {})
    if not isinstance(current, dict):
        raise ValueError("protocol profile must be a table")
    if current.get("schema_version", 1) not in (1, 2):
        raise ValueError("unsupported protocol schema_version")
    units = current.get("units", [])
    if not isinstance(units, list) or not all(isinstance(item, dict) for item in units):
        raise ValueError("protocol units must be an array of tables")
    return str(current.get("domain", "")), cast("list[dict[str, object]]", units)


def _persisted(domain: str, unit: dict[str, object]) -> ProtocolUnitDecl | None:
    if not {"ticket_type", "input_contract", "entry_action"} & unit.keys():
        return None
    contracts = unit.get("contracts")
    if not isinstance(contracts, list):
        raise ValueError("shared unit contracts must be a list")
    return ProtocolUnitDecl.model_validate(
        {
            "domain": domain,
            "unit": unit.get("name"),
            "contracts": [{"name": name} for name in contracts],
            "ticket": {
                "ticket_type": unit.get("ticket_type"),
                "input_contract": unit.get("input_contract"),
                "entry_action": unit.get("entry_action"),
            },
        }
    )


def _requested_unit(units: list[dict[str, object]], name: str) -> dict[str, object]:
    matches = [item for item in units if item.get("name") == name]
    if len(matches) > 1:
        raise ValueError("duplicate protocol unit declarations")
    return matches[0] if matches else {}


def _resolved(
    first: ProtocolScaffoldDecl,
    existing: ProtocolUnitDecl | None,
    supplied: ProtocolUnitDecl | None,
) -> ProtocolUnitDecl | None:
    if supplied is not None:
        if (supplied.domain, supplied.unit) != (first.domain, first.unit):
            raise ValueError("shared declaration must belong to this domain/unit")
        if existing is not None and supplied != existing:
            raise ValueError("shared unit declaration conflicts with persisted binding")
    return supplied or existing


def _actions(unit: dict[str, object]) -> list[dict[str, object]]:
    value = unit.get("protocols", [])
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError("unit protocols must be an array of tables")
    return cast("list[dict[str, object]]", value)


def _local_ticket_types(
    units: list[dict[str, object]], declarations: tuple[ProtocolScaffoldDecl, ...]
) -> list[object]:
    types = [action.get("ticket_type") for unit in units for action in _actions(unit)]
    types.extend(
        item.ticket.ticket_type for item in declarations if item.ticket is not None
    )
    return types


def _validate_ownership(
    units: list[dict[str, object]],
    declarations: tuple[ProtocolScaffoldDecl, ...],
    shared: ProtocolUnitDecl | None,
    domain: str,
) -> None:
    bindings = [
        item for unit in units if (item := _persisted(domain, unit)) is not None
    ]
    if shared is not None:
        bindings.append(shared)
    owners: dict[str, set[str]] = {}
    for item in bindings:
        owners.setdefault(item.ticket.ticket_type, set()).add(item.unit)
    if any(len(value) > 1 for value in owners.values()):
        raise ValueError("shared ticket type is already owned by another unit")
    local = _local_ticket_types(units, declarations)
    if any(identity in owners for identity in local):
        raise ValueError("local ticket conflicts with shared ticket type")


def _validate_references(
    declarations: tuple[ProtocolScaffoldDecl, ...],
    unit: dict[str, object],
    shared: ProtocolUnitDecl | None,
) -> None:
    expected = None if shared is None else shared.ticket.ticket_type
    if any(
        item.unit_ticket is not None and item.unit_ticket != expected
        for item in declarations
    ):
        raise ValueError("unit_ticket must reference the ticket of this domain/unit")
    if shared is not None:
        actions = {item.get("action") for item in _actions(unit)}
        actions.update(item.action for item in declarations)
        if shared.ticket.entry_action not in actions:
            raise ValueError("shared ticket entry_action must be declared")


def resolve_protocol_unit(
    metadata: str,
    declarations: tuple[ProtocolScaffoldDecl, ...],
    supplied: ProtocolUnitDecl | None,
) -> ProtocolUnitDecl | None:
    """Resolve only this unit; reject changed bindings and identity collisions."""
    if not declarations:
        raise ValueError("protocols must contain at least one declaration")
    first = declarations[0]
    domain, units = _units(metadata)
    if domain and domain != first.domain:
        raise ValueError("protocol domain conflicts with existing profile")
    unit = _requested_unit(units, first.unit)
    shared = _resolved(first, _persisted(first.domain, unit), supplied)
    _validate_ownership(units, declarations, shared, first.domain)
    _validate_references(declarations, unit, shared)
    return shared


def _unit_table(units: AoT, name: str) -> object:
    matching = next((item for item in units if item.get("name") == name), None)
    if matching is None:
        matching = table()
        matching["name"] = name
        matching["protocols"] = aot()
        units.append(matching)
    return matching


def merge_protocol_unit(metadata: str, declaration: ProtocolUnitDecl) -> str:
    """Persist one shared binding without changing existing actions."""
    from tomlkit.items import Table

    document = parse(metadata)
    profile = table_at(table_at(table_at(document, "tool"), "axm-init"), "protocols")
    profile["schema_version"] = 2
    profile["domain"] = declaration.domain
    units = profile.get("units")
    if units is None:
        units = aot()
        profile["units"] = units
    if not isinstance(units, AoT):
        raise ValueError("protocol units must be an array of tables")
    matching = _unit_table(units, declaration.unit)
    if not isinstance(matching, Table):
        raise ValueError("protocol unit must be a table")
    matching["contracts"] = [item.name for item in declaration.contracts]
    matching["ticket_type"] = declaration.ticket.ticket_type
    matching["input_contract"] = declaration.ticket.input_contract
    matching["entry_action"] = declaration.ticket.entry_action
    return dumps(document)
