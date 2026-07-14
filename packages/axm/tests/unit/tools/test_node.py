"""Unit tests for the AXMTool → DAG-node adapter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from axm.tools import ToolNodeError, tool_node
from axm.tools.base import ToolResult


class _Tool:
    """A fake AXMTool recording the kwargs it was called with."""

    def __init__(self, result: ToolResult) -> None:
        self._result = result
        self.seen: dict[str, object] = {}

    @property
    def name(self) -> str:
        return "fake"

    def execute(self, **kwargs: object) -> ToolResult:
        self.seen = kwargs
        return self._result


def _ep(name: str, obj: object) -> MagicMock:
    ep = MagicMock()
    ep.name = name
    ep.load.return_value = obj
    return ep


def _with_tool(tool: object, name: str = "ast_impact"):
    """Patch entry-point discovery to expose a single fake tool."""
    return patch(
        "axm.tools.node.entry_points_for", return_value={name: _ep(name, tool)}
    )


class TestPayloadMapping:
    def test_payload_keys_map_to_execute_by_name(self) -> None:
        """Payload keys arrive as same-named execute kwargs."""
        tool = _Tool(ToolResult(success=True, text="impact"))
        node = tool_node("ast_impact", returns={"blast_radius": "text"})
        with _with_tool(tool):
            node({"path": "/p", "symbol": "Foo"})
        assert tool.seen == {"path": "/p", "symbol": "Foo"}

    def test_rename_map_overrides_param_name(self) -> None:
        """A param whose mem key differs is mapped via the rename map."""
        tool = _Tool(ToolResult(success=True, text="x"))
        node = tool_node("ast_impact", args={"symbol": "target"}, returns={"r": "text"})
        with _with_tool(tool):
            node({"path": "/p", "target": "Bar"})
        assert tool.seen == {"path": "/p", "symbol": "Bar"}
        assert "target" not in tool.seen  # the mem key is not leaked as a kwarg


class TestOutputShaping:
    def test_text_source_returns_result_text(self) -> None:
        """A write sourced from 'text' returns ToolResult.text."""
        tool = _Tool(ToolResult(success=True, text="the body"))
        node = tool_node("ast_impact", returns={"source_body": "text"})
        with _with_tool(tool):
            out = node({"path": "/p", "symbol": "F"})
        assert out == {"source_body": "the body"}

    def test_data_key_source_returns_that_data_field(self) -> None:
        """A write sourced from a data key returns that field of ToolResult.data."""
        tool = _Tool(ToolResult(success=True, data={"callers": ["a", "b"]}))
        node = tool_node("ast_impact", returns={"callers": "callers"})
        with _with_tool(tool):
            out = node({"path": "/p", "symbol": "F"})
        assert out == {"callers": ["a", "b"]}

    def test_missing_data_key_raises(self) -> None:
        """A write sourced from an absent data key fails loudly."""
        tool = _Tool(ToolResult(success=True, data={}))
        node = tool_node("ast_impact", returns={"x": "nope"})
        with _with_tool(tool), pytest.raises(ToolNodeError, match="no 'nope'"):
            node({"path": "/p", "symbol": "F"})


class TestFailFast:
    def test_unsuccessful_result_raises(self) -> None:
        """A tool returning success=False raises ToolNodeError (fail-fast)."""
        tool = _Tool(ToolResult(success=False, error="symbol required"))
        node = tool_node("ast_impact", returns={"r": "text"})
        with _with_tool(tool), pytest.raises(ToolNodeError, match="symbol required"):
            node({"path": "/p"})

    def test_unknown_tool_raises_with_registered_list(self) -> None:
        """An unregistered tool name raises, naming what is registered."""
        node = tool_node("ghost", returns={"r": "text"})
        with _with_tool(_Tool(ToolResult(success=True)), name="real"):
            with pytest.raises(ToolNodeError, match="No tool registered under 'ghost'"):
                node({})

    def test_bad_payload_key_raises_tool_node_error(self) -> None:
        """A payload key with no matching strict ``execute`` param → ToolNodeError.

        The adapter documents ``Raises: ToolNodeError`` — a raw ``TypeError`` from
        ``execute(**kwargs)`` must be wrapped, not leaked.
        """

        class _StrictTool:
            @property
            def name(self) -> str:
                return "strict"

            def execute(self, *, path: str = ".") -> ToolResult:
                return ToolResult(success=True, text="ok")

        node = tool_node("strict", returns={"r": "text"})
        with _with_tool(_StrictTool(), name="strict"):
            with pytest.raises(ToolNodeError, match="bad payload for execute"):
                node({"path": ".", "unexpected_key": 1})


class TestClassEntryPoint:
    def test_class_entry_point_is_instantiated(self) -> None:
        """An entry point loading to a class is instantiated before use."""
        instances: list[_Tool] = []

        class _Factory(_Tool):
            def __init__(self) -> None:
                super().__init__(ToolResult(success=True, text="ok"))
                instances.append(self)

        node = tool_node("ast_impact", returns={"r": "text"})
        with patch(
            "axm.tools.node.entry_points_for",
            return_value={"ast_impact": _ep("ast_impact", _Factory)},
        ):
            out = node({"path": "/p", "symbol": "F"})
        assert out == {"r": "ok"}
        assert len(instances) == 1  # the class was instantiated, not used raw
