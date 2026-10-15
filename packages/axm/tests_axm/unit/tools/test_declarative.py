"""Closed declarative metadata and the generic unbound/bound adapter."""

from __future__ import annotations

import copy
from types import SimpleNamespace
from typing import cast

import pytest

from axm import (
    DeclarativeTool,
    ToolResult,
    load_declarative_manifest,
    tool_scope_sha256,
    validate_declarative_schema,
)


@pytest.fixture
def raw():
    return {
        "schema_version": 1,
        "addon_id": "rugby",
        "bundle_sha256": "a" * 64,
        "tools": [
            {
                "name": "rugby_ui_select_match",
                "handler": "rugby_ui_select_match",
                "description": "Select",
                "inputSchema": {
                    "type": "object",
                    "properties": {"match": {"type": "string"}},
                    "required": ["match"],
                    "additionalProperties": False,
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {"match": {"type": "string"}},
                    "required": ["match"],
                    "additionalProperties": False,
                },
            }
        ],
    }


def test_schemas_are_detached_and_adapter_requires_binding(raw):
    manifest = load_declarative_manifest(raw)
    definition = manifest.tools[0]
    raw["tools"][0]["inputSchema"]["required"] = []
    definition.input_schema["required"] = []
    assert definition.input_schema["required"] == ["match"]
    unavailable = DeclarativeTool(definition).execute(match="A")
    assert not unavailable.success
    assert unavailable.data == {"status": "unavailable"}
    calls = []

    def invoke(name, arguments):
        calls.append((name, arguments))
        return ToolResult(success=True, data=arguments)

    adapter = DeclarativeTool(definition, invoke)
    assert adapter.execute(match="A").data == {"match": "A"}
    assert len(calls) == 1
    assert not adapter.execute(match="A", target="elsewhere").success
    assert len(calls) == 1


def test_invalid_success_result_is_not_reported_as_success(raw):
    definition = load_declarative_manifest(raw).tools[0]
    adapter = DeclarativeTool(
        definition,
        lambda name, args: ToolResult(success=True, data={"wrong": "result"}),
    )
    assert not adapter.execute(match="A").success


def test_ui_adapter_never_promotes_malformed_success_flag(raw):
    definition = load_declarative_manifest(raw).tools[0]
    adapter = DeclarativeTool(
        definition,
        lambda name, args: cast(ToolResult, SimpleNamespace(success=1, data=args)),
    )
    result = adapter.execute(match="A")
    assert result.success is False
    assert "success must be a boolean" in result.error


@pytest.mark.parametrize("keyword", ["$ref", "$dynamicRef", "$recursiveRef", "$id"])
def test_shared_schema_validator_refuses_remote_reference_at_any_depth(keyword):
    with pytest.raises(ValueError):
        validate_declarative_schema(
            {
                "type": "object",
                "properties": {"nested": {keyword: "https://external.test/schema"}},
            }
        )


@pytest.mark.parametrize(
    "extra",
    [
        {"$schema": "https://external.test/dialect"},
        {"$vocabulary": {"https://external.test/rules": True}},
        {"$recursiveRef": "#"},
        {"$recursiveAnchor": True},
    ],
)
def test_shared_schema_validator_refuses_unsupported_dialects(extra):
    with pytest.raises(ValueError):
        validate_declarative_schema({"type": "object", **extra})


def test_shared_schema_validator_accepts_local_refs_and_returns_detached_schema():
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import ValidationError

    source = {
        "type": "object",
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": {"text": {"type": "string"}},
        "properties": {
            "first": {"$ref": "#/$defs/text"},
            "second": {"$dynamicRef": "#/$defs/text"},
        },
    }
    detached = validate_declarative_schema(source)
    source["properties"]["first"]["$ref"] = "https://external.test/schema"
    validator = Draft202012Validator(detached)
    validator.validate({"first": "safe", "second": "safe"})
    with pytest.raises(ValidationError):
        validator.validate({"first": 1})
    with pytest.raises(ValidationError):
        validator.validate({"second": 1})


@pytest.mark.parametrize(
    "position",
    [
        lambda child: {"allOf": [child]},
        lambda child: {"additionalProperties": child},
        lambda child: {"$defs": {"definition": child}},
        lambda child: {"if": child},
    ],
)
def test_nested_schema_positions_cannot_hide_remote_references(position):
    with pytest.raises(ValueError):
        validate_declarative_schema(
            {"type": "object", **position({"$ref": "https://external.test/schema"})}
        )


def test_schema_annotations_and_property_names_are_data_not_reference_keywords():
    detached = validate_declarative_schema(
        {
            "type": "object",
            "properties": {"$ref": {"type": "string"}},
            "examples": [{"$ref": "https://data.test/not-a-schema"}],
        }
    )
    assert detached["properties"] == {"$ref": {"type": "string"}}


@pytest.mark.parametrize(
    "mutation",
    [
        lambda raw: raw.update(schema_version=2),
        lambda raw: raw.update(schema_version=True),
        lambda raw: raw.update(extra="unknown"),
        lambda raw: raw.update(bundle_sha256="not-hash"),
        lambda raw: raw["tools"].append(copy.deepcopy(raw["tools"][0])),
        lambda raw: raw["tools"][0].update(handler="other"),
        lambda raw: raw["tools"][0].update(name="axm_call", handler="axm_call"),
        lambda raw: raw["tools"][0]["inputSchema"].update(type="array"),
        lambda raw: raw["tools"][0]["inputSchema"].update(
            {"$ref": "https://external.test/schema"}
        ),
        lambda raw: raw["tools"][0]["inputSchema"].update(
            {"$schema": "http://json-schema.org/draft-07/schema#"}
        ),
    ],
)
def test_invalid_contract_is_rejected(raw, mutation):
    mutation(raw)
    with pytest.raises(ValueError):
        load_declarative_manifest(raw)


def test_cli_json_arguments_use_same_bound_adapter(raw, capsys):
    from axm.cli import build_command_for_tool

    definition = load_declarative_manifest(raw).tools[0]
    tool = DeclarativeTool(
        definition, lambda name, args: ToolResult(success=True, data=args)
    )
    command = build_command_for_tool(definition.name, tool)
    command(arguments='{"match":"A"}')
    assert '"A"' in capsys.readouterr().out


def test_scope_hash_is_order_independent_and_positive():
    assert tool_scope_sha256(frozenset({"b", "a"})) == tool_scope_sha256(
        frozenset({"a", "b"})
    )
    assert tool_scope_sha256(frozenset({"a"})) != tool_scope_sha256(frozenset())
