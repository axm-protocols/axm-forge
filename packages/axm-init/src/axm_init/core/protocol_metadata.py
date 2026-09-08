from __future__ import annotations

from tomlkit import TOMLDocument, aot, dumps, parse, table
from tomlkit.items import AoT, Table

from axm_init.models.protocol_scaffold import ProtocolScaffoldDecl

__all__ = ["merge_protocol_metadata"]

type _TomlContainer = TOMLDocument | Table


def _table_at(container: _TomlContainer, key: str) -> Table:
    value = container.get(key)
    if value is None:
        created = table()
        container[key] = created
        return created
    if not isinstance(value, Table):
        msg = f"{key!r} must be a TOML table"
        raise ValueError(msg)
    return value


def _array_of_tables_at(container: Table, key: str) -> AoT:
    value = container.get(key)
    if value is None:
        created = aot()
        container[key] = created
        return created
    if not isinstance(value, AoT):
        msg = f"{key!r} must be a TOML array of tables"
        raise ValueError(msg)
    return value


def _protocol_table(declaration: ProtocolScaffoldDecl) -> Table:
    protocol = table()
    protocol["action"] = declaration.action
    protocol["state"] = "draft"
    protocol["contracts"] = [contract.name for contract in declaration.contracts]
    protocol["nodes"] = [node.name for node in declaration.nodes]
    protocol["prompts"] = [prompt.name for prompt in declaration.prompts]
    protocol["phases"] = [phase.name for phase in declaration.phases]
    if declaration.ticket is not None:
        protocol["ticket_type"] = declaration.ticket.ticket_type
        protocol["input_contract"] = declaration.ticket.input_contract
    return protocol


def _find_table(items: AoT, key: str, value: str) -> tuple[int, Table] | None:
    for index, item in enumerate(items):
        if item.get(key) == value:
            return index, item
    return None


def merge_protocol_metadata(
    metadata: str,
    declaration: ProtocolScaffoldDecl,
) -> str:
    """Merge one validated draft protocol declaration into TOML metadata."""
    document = parse(metadata)
    tool = _table_at(document, "tool")
    axm_init = _table_at(tool, "axm-init")
    profile = _table_at(axm_init, "protocols")

    profile["schema_version"] = 1
    profile["domain"] = declaration.domain

    units = _array_of_tables_at(profile, "units")
    unit_match = _find_table(units, "name", declaration.unit)
    if unit_match is None:
        unit = table()
        unit["name"] = declaration.unit
        unit["protocols"] = aot()
        units.append(unit)
    else:
        _, unit = unit_match

    protocols = _array_of_tables_at(unit, "protocols")
    desired = _protocol_table(declaration)
    protocol_match = _find_table(protocols, "action", declaration.action)
    if protocol_match is None:
        protocols.append(desired)
    else:
        index, current = protocol_match
        if dumps(current) == dumps(desired):
            return metadata
        protocols[index] = desired

    return dumps(document)
