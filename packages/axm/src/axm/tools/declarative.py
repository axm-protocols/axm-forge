"""Versioned, frontend-independent declarative tool contracts."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from axm.tools.base import ToolResult

__all__ = [
    "DeclarativeTool",
    "DeclarativeToolDefinition",
    "DeclarativeToolManifest",
    "load_declarative_manifest",
    "tool_scope_sha256",
    "validate_declarative_schema",
]

_NAME = re.compile(r"^[a-z][a-z0-9_]{0,127}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_RESERVED = frozenset(
    {"axm_search", "axm_describe", "axm_call", "axm_capabilities", "list_tools"}
)


def tool_scope_sha256(names: frozenset[str]) -> str:
    """Fingerprint a positive tool list; no provider-specific spelling."""
    wire = json.dumps(sorted(names), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(wire.encode()).hexdigest()


def _validate_reference(key: str, child: object) -> None:
    if key in {"$ref", "$dynamicRef", "$recursiveRef", "$id"} and (
        not isinstance(child, str) or not child.startswith("#")
    ):
        raise ValueError("tool schemas allow local references only")
    if key == "$schema" and child != "https://json-schema.org/draft/2020-12/schema":
        raise ValueError("tool schemas use JSON Schema 2020-12")
    if key in {"$vocabulary", "$recursiveAnchor", "$recursiveRef"}:
        raise ValueError("unsupported schema dialect keyword; use JSON Schema 2020-12")


def _local_references(value: object) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            _validate_reference(key, child)
            for nested in _schema_children(key, child):
                _local_references(nested)


def _schema_children(key: str, value: object) -> list[object]:
    if key in {
        "$defs",
        "definitions",
        "properties",
        "patternProperties",
        "dependentSchemas",
    }:
        return list(value.values()) if isinstance(value, dict) else []
    if key in {"allOf", "anyOf", "oneOf", "prefixItems"}:
        return value if isinstance(value, list) else []
    if key in {
        "additionalProperties",
        "unevaluatedProperties",
        "items",
        "unevaluatedItems",
        "contains",
        "propertyNames",
        "if",
        "then",
        "else",
        "not",
        "contentSchema",
    }:
        return [value]
    return []


def validate_declarative_schema(schema: Mapping[str, object]) -> dict[str, object]:
    """Return a detached object schema validated offline for tools or snapshots.

    Only the supported 2020-12 dialect and local references are accepted. Remote
    IDs/vocabularies and legacy recursive dialect keywords cannot weaken it.
    """
    encoded = json.dumps(dict(schema), allow_nan=False)
    detached = json.loads(encoded)
    if detached.get("type") != "object":
        raise ValueError("tool schema root must be an object")
    _local_references(detached)
    try:
        Draft202012Validator.check_schema(detached)
    except SchemaError as exc:
        raise ValueError(f"invalid tool schema: {exc.message}") from exc
    return cast(dict[str, object], detached)


def _schema_json(schema: Mapping[str, object]) -> str:
    return json.dumps(validate_declarative_schema(schema), allow_nan=False)


@dataclass(frozen=True, init=False)
class DeclarativeToolDefinition:
    """Immutable tool metadata; schemas are detached on every access."""

    name: str
    description: str
    handler: str
    execution: str
    _input_json: str
    _output_json: str

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: Mapping[str, object],
        output_schema: Mapping[str, object],
        handler: str,
    ) -> None:
        if not _NAME.fullmatch(name) or name in _RESERVED:
            raise ValueError(f"invalid or reserved declarative tool name: {name}")
        if not description.strip() or handler != name:
            raise ValueError("description is required and handler must equal tool name")
        for key, value in (
            ("name", name),
            ("description", description),
            ("handler", handler),
            ("execution", "ui"),
            ("_input_json", _schema_json(input_schema)),
            ("_output_json", _schema_json(output_schema)),
        ):
            object.__setattr__(self, key, value)

    @property
    def input_schema(self) -> dict[str, object]:
        """Detached JSON Schema for functional arguments, without routing fields."""
        return cast(dict[str, object], json.loads(self._input_json))

    @property
    def output_schema(self) -> dict[str, object]:
        """Detached JSON Schema for successful ToolResult.data."""
        return cast(dict[str, object], json.loads(self._output_json))

    def validate_input(self, arguments: Mapping[str, object]) -> None:
        """Reject malformed/non-JSON arguments before contacting any view."""
        detached = json.loads(json.dumps(dict(arguments), allow_nan=False))
        Draft202012Validator(self.input_schema).validate(detached)

    def validate_result(self, result: ToolResult) -> ToolResult:
        """Validate successful data; failures retain their structural signal."""
        if not isinstance(result.success, bool):
            raise ValueError("malformed ToolResult: success must be a boolean")
        if result.success:
            detached = json.loads(json.dumps(result.data, allow_nan=False))
            Draft202012Validator(self.output_schema).validate(detached)
        return result


@dataclass(frozen=True)
class DeclarativeToolManifest:
    """One addon bundle's closed tool declarations."""

    schema_version: int
    addon_id: str
    bundle_sha256: str
    tools: tuple[DeclarativeToolDefinition, ...]

    def __post_init__(self) -> None:
        _validate_manifest(self)


def _validate_manifest(manifest: DeclarativeToolManifest) -> None:
    if type(manifest.schema_version) is not int or manifest.schema_version != 1:
        raise ValueError("unsupported declarative manifest schema_version")
    if not manifest.addon_id or not _HASH.fullmatch(manifest.bundle_sha256):
        raise ValueError("addon_id and lowercase bundle SHA256 are required")
    if not isinstance(manifest.tools, tuple) or not all(
        isinstance(tool, DeclarativeToolDefinition) for tool in manifest.tools
    ):
        raise ValueError("manifest tools must be an immutable definition tuple")
    names = [tool.name for tool in manifest.tools]
    if len(names) != len(set(names)):
        raise ValueError("duplicate declarative tool name")


def _object(value: object, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"expected exact manifest fields: {sorted(keys)}")
    return cast(dict[str, object], value)


def _string(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("manifest string field expected")
    return value


def _definition(raw: object) -> DeclarativeToolDefinition:
    data = _object(
        raw, {"name", "description", "inputSchema", "outputSchema", "handler"}
    )
    schemas = (data["inputSchema"], data["outputSchema"])
    if not all(isinstance(schema, dict) for schema in schemas):
        raise ValueError("tool schemas must be JSON objects")
    return DeclarativeToolDefinition(
        name=_string(data["name"]),
        description=_string(data["description"]),
        input_schema=cast(dict[str, object], schemas[0]),
        output_schema=cast(dict[str, object], schemas[1]),
        handler=_string(data["handler"]),
    )


def load_declarative_manifest(raw: Mapping[str, object]) -> DeclarativeToolManifest:
    """Validate a JSON manifest from a trusted installed package.

    Extra fields, remote schema references, versions and collisions are refused.
    This validates metadata only: the host verifies the mounted bundle.
    """
    data = _object(dict(raw), {"schema_version", "addon_id", "bundle_sha256", "tools"})
    if not isinstance(data["tools"], list):
        raise ValueError("manifest tools must be a list")
    version = data["schema_version"]
    if type(version) is not int:
        raise ValueError("schema_version must be an integer")
    return DeclarativeToolManifest(
        schema_version=version,
        addon_id=_string(data["addon_id"]),
        bundle_sha256=_string(data["bundle_sha256"]),
        tools=tuple(_definition(tool) for tool in data["tools"]),
    )


class DeclarativeTool:
    """Common AXMTool adapter, unavailable without an explicit host binding."""

    expose_directly = True
    tags = frozenset({"ui", "declarative"})

    def __init__(
        self,
        definition: DeclarativeToolDefinition,
        invoke: Callable[[str, dict[str, object]], ToolResult] | None = None,
    ) -> None:
        self.definition = definition
        self._invoke = invoke
        self.__doc__ = definition.description

    @property
    def name(self) -> str:
        """Canonical name shared by CLI, nodes and MCP."""
        return self.definition.name

    def execute(self, **kwargs: object) -> ToolResult:
        """Validate and invoke the host binding, never an ambient view."""
        try:
            self.definition.validate_input(kwargs)
            if self._invoke is None:
                return ToolResult(
                    success=False,
                    data={"status": "unavailable"},
                    error="UI tool unavailable: no host view binding",
                )
            return self.definition.validate_result(self._invoke(self.name, kwargs))
        except (ValidationError, ValueError, TypeError) as exc:
            return ToolResult(success=False, error=f"invalid UI tool contract: {exc}")
