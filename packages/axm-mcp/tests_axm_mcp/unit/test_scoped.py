"""Pure factory validation fails before constructing an executable scope."""

from __future__ import annotations

import json
from typing import cast

import pytest
from axm import ToolResult, load_declarative_manifest

from axm_mcp import create_scoped_mcp_app
from axm_mcp.scoped import _backend_result, _result
from axm_mcp.wrapping import RenderedText


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


@pytest.mark.parametrize("tool_result", [True, False])
@pytest.mark.parametrize("success", [None, 0, 1, "true"])
def test_backend_response_refuses_non_boolean_success(success, tool_result):
    result = _backend_result({"success": success}, tool_result=tool_result)
    assert result.is_error is True
    assert result.structured_content is None
    assert "success must be a boolean" in result.content[0].text


@pytest.mark.parametrize("success", [True, False])
def test_rendered_text_is_the_whole_backend_answer(success):
    result = _backend_result(RenderedText("compact", success), tool_result=True)
    assert result.is_error is (not success)
    assert result.structured_content is None
    assert [item.text for item in result.content] == ["compact"]


def test_plain_dispatcher_data_needs_no_success_envelope():
    payload = {"answer": 42, "text": "ordinary data field"}
    result = _backend_result(payload, tool_result=False)
    assert result.is_error is False
    assert result.structured_content is None
    assert json.loads(result.content[0].text) == payload


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
