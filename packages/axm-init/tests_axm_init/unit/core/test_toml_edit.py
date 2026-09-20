from __future__ import annotations

import pytest
from tomlkit import parse
from tomlkit.items import Table

from axm_init.core.toml_edit import table_at


def test_table_at_returns_the_existing_table() -> None:
    """AC1: an already-declared table is returned as-is, values intact."""
    document = parse('[tool]\nname = "demo"\n')

    result = table_at(document, "tool")

    assert isinstance(result, Table)
    assert result["name"] == "demo"


def test_table_at_creates_and_attaches_a_missing_table() -> None:
    """AC1: a missing branch is created empty and attached to the container."""
    document = parse("")

    created = table_at(document, "tool")
    created["domain"] = "vision"

    assert document["tool"] is created
    assert parse(document.as_string())["tool"]["domain"] == "vision"


def test_table_at_nests_through_an_intermediate_table() -> None:
    """AC1: the helper chains, a table being a valid container itself."""
    document = parse("")

    profile = table_at(table_at(document, "tool"), "axm-init")
    profile["schema_version"] = 1

    assert parse(document.as_string())["tool"]["axm-init"]["schema_version"] == 1


def test_table_at_rejects_a_key_holding_a_non_table() -> None:
    """AC2: a scalar squatting the key is an error, never silently replaced."""
    document = parse('tool = "not-a-table"\n')

    with pytest.raises(ValueError, match="must be a TOML table"):
        table_at(document, "tool")
