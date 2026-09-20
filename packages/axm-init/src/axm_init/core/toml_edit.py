"""Shared tomlkit container helpers for metadata merging."""

from __future__ import annotations

from tomlkit import TOMLDocument, table
from tomlkit.items import Table

__all__ = ["TomlContainer", "table_at"]


type TomlContainer = TOMLDocument | Table


def table_at(container: TomlContainer, key: str) -> Table:
    """Return the table at *key*, creating an empty one when absent.

    Args:
        container: The document or table to read the branch from.
        key: The key holding the nested table.

    Returns:
        The existing table, or the freshly created and attached one.

    Raises:
        ValueError: When *key* already holds a non-table value.
    """
    value = container.get(key)
    if value is None:
        created = table()
        container[key] = created
        return created
    if not isinstance(value, Table):
        msg = f"{key!r} must be a TOML table"
        raise ValueError(msg)
    return value
