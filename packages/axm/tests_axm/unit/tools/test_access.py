"""Positive tool scopes cannot widen via nesting, overrides or cached nodes."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import cast

import pytest

from axm import (
    AXMTool,
    ToolAccessDenied,
    ToolResult,
    tool_access_scope,
    tool_execution_guard,
    tool_node,
)
from axm.tools import load_tool, override_tools
from axm.tools.access import (
    check_tool_execution,
    has_tool_execution_guard,
    require_tool_access,
    tool_is_allowed,
)
from axm.tools.dependency_reads import dependency_read_context
from axm.tools.discovery import tool_entry_points
from axm.tools.write_scope import WriteContract


def test_nested_scope_intersects_and_restores():
    assert tool_is_allowed("other")
    with tool_access_scope(frozenset({"first"})):
        assert tool_is_allowed("first")
        assert not tool_is_allowed("other")
        with tool_access_scope(frozenset({"first", "other"})):
            assert not tool_is_allowed("other")
        assert tool_is_allowed("first")
    assert tool_is_allowed("other")


def test_empty_scope_filters_discovery_and_rejects_even_override():
    class Tool:
        name = "hidden"

        def execute(self, **kwargs):
            return ToolResult(success=True, data={"value": 1})

    with override_tools({"hidden": Tool()}):
        assert load_tool("hidden").execute().success
        node = tool_node("hidden", returns={"value": "value"})
        assert node({}) == {"value": 1}
        with tool_access_scope(frozenset()):
            assert tool_entry_points() == {}
            with pytest.raises(ToolAccessDenied):
                load_tool("hidden")
            with pytest.raises(ToolAccessDenied):
                node({})


def test_direct_gate_rejects_undeclared_name():
    with tool_access_scope(frozenset({"visible"})):
        require_tool_access("visible")
        with pytest.raises(ToolAccessDenied):
            require_tool_access("hidden")


def test_resolved_handle_retains_lease_and_original_signature():
    calls = []
    live = {"value": True}

    class Tool:
        name = "visible"
        description = "Preserved metadata"

        def execute(self, *, value: int = 1) -> ToolResult:
            calls.append(value)
            return ToolResult(success=True, data={"value": value})

    def guard(name, arguments, execute):
        if not live["value"]:
            raise PermissionError("lease revoked")

    original = cast(AXMTool, Tool())
    with override_tools({"visible": original}):
        assert load_tool("visible") is original
        with tool_access_scope(frozenset({"visible"})), tool_execution_guard(guard):
            resolved = load_tool("visible")
            assert inspect.signature(resolved.execute) == inspect.signature(
                original.execute
            )
            assert resolved.description == original.description
            assert resolved.execute(value=2).data == {"value": 2}
        live["value"] = False
        with pytest.raises(PermissionError, match="lease revoked"):
            resolved.execute(value=3)
    assert calls == [2]


def test_cached_node_uses_current_guard_not_previous_request(monkeypatch):
    from axm.tools import node as nodes

    calls = []
    leases = {"first": True, "second": True}

    class Tool:
        name = "visible"

        def execute(self, *, value: int) -> ToolResult:
            calls.append(value)
            return ToolResult(success=True, data={"value": value})

    monkeypatch.setattr(nodes, "_load_tool", lambda name: Tool())
    cached = tool_node("visible", returns={"value": "value"})

    def policy(lease) -> Callable[[str, dict[str, object], object], None]:
        def guard(name, arguments, execute):
            if not leases[lease]:
                raise PermissionError("lease revoked")

        return guard

    with tool_execution_guard(policy("first")):
        assert cached({"value": 1}) == {"value": 1}
    leases["first"] = False
    with tool_execution_guard(policy("second")):
        assert cached({"value": 2}) == {"value": 2}
        leases["second"] = False
        with pytest.raises(PermissionError, match="lease revoked"):
            cached({"value": 3})
    assert calls == [1, 2]


def test_execution_guards_nest_restore_and_normalize():
    seen = []

    class Tool:
        name = "visible"

        def execute(self, **kwargs):
            return ToolResult(success=True, data=kwargs)

    def outer(name, arguments, execute):
        seen.append("outer")
        arguments["normalized"] = "owned"

    def inner(name, arguments, execute):
        seen.append("inner")
        raise PermissionError("inner revoked")

    with override_tools({"visible": Tool()}), tool_execution_guard(outer):
        resolved = load_tool("visible")
        with tool_execution_guard(inner):
            with pytest.raises(PermissionError, match="inner revoked"):
                resolved.execute()
        assert resolved.execute().data == {"normalized": "owned"}
    assert seen == ["outer", "inner", "outer"]


def test_execution_guard_lifecycle_and_empty_name_scope():
    checks = []

    def guard(name, arguments, execute):
        checks.append(name)

    assert not has_tool_execution_guard()
    with tool_execution_guard(guard):
        assert has_tool_execution_guard()
        check_tool_execution("visible", {}, None)
        with tool_access_scope(frozenset()):
            with pytest.raises(ToolAccessDenied):
                check_tool_execution("hidden", {}, None)
    assert not has_tool_execution_guard()
    assert checks == ["visible"]


def test_mutable_name_scope_is_rejected():
    with pytest.raises(ValueError, match="immutable"):
        with tool_access_scope(cast(frozenset[str], {"visible"})):
            pytest.fail("mutable scope accepted")


def test_retained_handle_cannot_replace_live_explicit_denial_with_origin_contract():
    from axm import require_read_path

    class Tool:
        name = "visible"

        def execute(self) -> ToolResult:
            require_read_path("/owned/data.db")
            return ToolResult(success=True)

    origin = WriteContract(execution_root="/owned")
    with override_tools({"visible": cast(AXMTool, Tool())}):
        with dependency_read_context(origin), tool_access_scope(frozenset({"visible"})):
            retained = load_tool("visible")
        with dependency_read_context(None):
            with pytest.raises(PermissionError, match="read authority missing"):
                retained.execute()
