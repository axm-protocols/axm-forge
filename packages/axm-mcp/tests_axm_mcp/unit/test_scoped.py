"""Pure factory validation fails before constructing an executable scope."""

from __future__ import annotations

from typing import cast

import pytest
from axm import ToolResult, load_declarative_manifest

from axm_mcp import create_scoped_mcp_app
from axm_mcp.scoped import _result


def test_response_constructor_cannot_promote_malformed_ui_success():
    result = _result(ToolResult(success=cast(bool, 1)), ui=True)
    assert result.is_error is True
    assert result.structured_content["success"] is False
    assert "success must be a boolean" in result.content[0].text


def test_factory_refuses_mutable_or_reserved_scope():
    async def invoke(name, arguments):
        raise AssertionError("invalid scope reached invoker")

    for allowed in ({"unexpected"}, frozenset({"axm_call"})):
        with pytest.raises(ValueError):
            create_scoped_mcp_app(
                allowed_tools=allowed,
                manifest=None,
                invoke=invoke,
                authorize=lambda scope: True,
                policy_revision="r",
                tools={},
            )


def test_manifest_cannot_shadow_backend():
    name = "fixture_ui_read"
    manifest = load_declarative_manifest(
        {
            "schema_version": 1,
            "addon_id": "fixture",
            "bundle_sha256": "a" * 64,
            "tools": [
                {
                    "name": name,
                    "handler": name,
                    "description": "Read",
                    "inputSchema": {"type": "object"},
                    "outputSchema": {"type": "object"},
                }
            ],
        }
    )

    class Backend:
        name = "backend"

        def execute(self, **kwargs):
            return ToolResult(success=True)

    async def invoke(name, arguments):
        raise AssertionError("collision reached invoker")

    with pytest.raises(ValueError, match="collision"):
        create_scoped_mcp_app(
            allowed_tools=frozenset({name}),
            manifest=manifest,
            invoke=invoke,
            authorize=lambda scope: True,
            policy_revision="r",
            tools={name: Backend()},
        )
