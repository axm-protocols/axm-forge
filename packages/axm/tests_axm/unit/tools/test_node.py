"""Unit tests for the AXMTool → DAG-node adapter."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from axm.tools import ToolNodeError, override_tools, tool_node
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

    def test_text_sentinel_wins_over_data_text_key(self) -> None:
        """'text' source routes to ToolResult.text even when data has a 'text' key.

        Pins the documented precedence (AC2): the ``"text"`` sentinel is checked
        before any ``ToolResult.data`` lookup, so a ``data["text"]`` field is
        unreachable through the *returns* shortcut. Guard-rail against a silent
        future divergence where the data key could shadow the sentinel.
        """
        tool = _Tool(
            ToolResult(success=True, data={"text": "DATA_VAL"}, text="TEXT_VAL")
        )
        node = tool_node("ast_impact", returns={"body": "text"})
        with _with_tool(tool):
            out = node({"path": "/p", "symbol": "F"})
        assert out == {"body": "TEXT_VAL"}  # sentinel wins, not "DATA_VAL"

    def test_docstring_documents_text_sentinel_collision(self) -> None:
        """Docstring warns 'text' shadows any data['text'] key (AC1)."""
        doc = tool_node.__doc__ or ""
        assert "text" in doc.lower()
        assert 'data["text"]' in doc
        assert "unreachable" in doc.lower()

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

    def test_unsuccessful_result_data_can_be_explicitly_observed(self) -> None:
        """Observation nodes may consume structured failure evidence opt-in."""
        cases = [{"node_id": "tests/test_x.py::test_x", "outcome": "failed"}]
        tool = _Tool(ToolResult(success=False, data={"cases": cases}))
        node = tool_node(
            "audit_test",
            returns={"cases": "cases"},
            allow_failure_data=True,
        )

        with _with_tool(tool, name="audit_test"):
            out = node({"path": "/p"})

        assert out == {"cases": cases}

    def test_failure_data_opt_in_still_requires_every_declared_write(self) -> None:
        """An empty failed result cannot masquerade as measured evidence."""
        tool = _Tool(
            ToolResult(success=False, data={}, error="pytest environment failed")
        )
        node = tool_node(
            "audit_test",
            returns={"cases": "cases"},
            allow_failure_data=True,
        )

        with (
            _with_tool(tool, name="audit_test"),
            pytest.raises(
                ToolNodeError,
                match=r"pytest environment failed.*no 'cases'",
            ),
        ):
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


class TestResolutionMemoized:
    def test_tool_resolved_once_across_two_invocations(self) -> None:
        """The entry points are scanned once, not on every closure call (AC1)."""
        tool = _Tool(ToolResult(success=True, text="impact"))
        node = tool_node("ast_impact", returns={"r": "text"})
        with patch(
            "axm.tools.node.entry_points_for",
            return_value={"ast_impact": _ep("ast_impact", tool)},
        ) as eps:
            first = node({"path": "/p", "symbol": "F"})
            second = node({"path": "/p", "symbol": "F"})
        assert eps.call_count == 1
        assert first == second == {"r": "impact"}

    def test_building_node_resolves_nothing_late_binding(self) -> None:
        """Constructing the node triggers no entry-point resolution (AC2)."""
        with patch("axm.tools.node.entry_points_for") as eps:
            tool_node("ast_impact", returns={"r": "text"})
        assert eps.call_count == 0


def _text(value: str) -> ToolResult:
    return ToolResult(success=True, data={}, text=value)


class TestOverrideTools:
    """``override_tools`` substitutes a tool for the dynamic extent of a block."""

    def test_override_wins_over_entry_point_without_loading_it(self) -> None:
        ep = _ep("ast_impact", _Tool(_text("real")))
        fake = _Tool(_text("fake"))
        node = tool_node("ast_impact", returns={"out": "text"})
        with patch("axm.tools.node.entry_points_for", return_value={"ast_impact": ep}):
            with override_tools({"ast_impact": fake}):
                assert node({"x": 1}) == {"out": "fake"}
        assert fake.seen == {"x": 1}
        ep.load.assert_not_called()

    def test_override_does_not_leak_past_its_block(self) -> None:
        real, fake = _Tool(_text("real")), _Tool(_text("fake"))
        node = tool_node("ast_impact", returns={"out": "text"})
        with _with_tool(real):
            with override_tools({"ast_impact": fake}):
                assert node({}) == {"out": "fake"}
            assert node({}) == {"out": "real"}

    def test_override_is_never_memoized_and_shadows_a_memoized_real_tool(self) -> None:
        real, fake = _Tool(_text("real")), _Tool(_text("fake"))
        node = tool_node("ast_impact", returns={"out": "text"})
        with _with_tool(real):
            assert node({}) == {"out": "real"}  # real tool now cached in the node
            with override_tools({"ast_impact": fake}):
                assert node({}) == {"out": "fake"}
            assert node({}) == {"out": "real"}

    def test_nested_blocks_add_and_shadow_then_restore(self) -> None:
        outer_a, outer_b, inner_a = (
            _Tool(_text("outer-a")),
            _Tool(_text("outer-b")),
            _Tool(_text("inner-a")),
        )
        node_a = tool_node("tool_a", returns={"out": "text"})
        node_b = tool_node("tool_b", returns={"out": "text"})
        with override_tools({"tool_a": outer_a, "tool_b": outer_b}):
            with override_tools({"tool_a": inner_a}):
                assert node_a({}) == {"out": "inner-a"}
                assert node_b({}) == {"out": "outer-b"}
            assert node_a({}) == {"out": "outer-a"}

    def test_unknown_names_are_not_resolved_by_an_unrelated_override(self) -> None:
        node = tool_node("nope", returns={"out": "text"})
        with patch("axm.tools.node.entry_points_for", return_value={}):
            with override_tools({"other": _Tool(_text("x"))}):
                with pytest.raises(ToolNodeError, match="No tool registered"):
                    node({})

    def test_override_follows_asyncio_to_thread_like_the_dag_runtime(self) -> None:
        """axm_dag runs sync python nodes via ``asyncio.to_thread``; the
        substitution must travel with that context switch."""
        fake = _Tool(_text("fake"))
        node = tool_node("ast_impact", returns={"out": "text"})

        async def run_like_a_node() -> dict[str, object]:
            return await asyncio.to_thread(node, {})

        with patch("axm.tools.node.entry_points_for", return_value={}):
            with override_tools({"ast_impact": fake}):
                assert asyncio.run(run_like_a_node()) == {"out": "fake"}


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
