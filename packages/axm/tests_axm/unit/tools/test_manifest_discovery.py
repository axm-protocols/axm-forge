"""Unbound manifest references have no global view fallback."""

from __future__ import annotations

from axm import DeclarativeToolDefinition
from axm.tools.manifest_discovery import DeclarativeToolReference


def test_reference_loads_same_definition_without_binding():
    definition = DeclarativeToolDefinition(
        name="fixture_ui_read",
        description="Read",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        handler="fixture_ui_read",
    )
    reference = DeclarativeToolReference("fixture_ui_read", "fixture", definition)
    adapter = reference.load()
    assert adapter.definition == definition
    assert reference.group == "axm.tool_manifests"
    assert not adapter.execute().success
