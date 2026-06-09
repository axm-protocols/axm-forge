"""Tests for AXMTool and ToolResult shared interface."""

from __future__ import annotations

import dataclasses
from typing import Any, ClassVar

import pytest

from axm.tools.base import AXMTool, ToolMetadata, ToolResult, tool_metadata

# ── ToolResult ─────────────────────────────────────────────────────────────────


class TestToolResult:
    """Tests for the ToolResult dataclass."""

    def test_success_result(self) -> None:
        """A successful result has success=True and no error."""
        result = ToolResult(success=True, data={"key": "value"})
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None

    def test_failure_result(self) -> None:
        """A failed result has success=False and an error message."""
        result = ToolResult(success=False, error="something went wrong")
        assert result.success is False
        assert result.error == "something went wrong"
        assert result.data == {}

    def test_default_data_is_empty_dict(self) -> None:
        """Default data is an empty dict, not shared across instances."""
        r1 = ToolResult(success=True)
        r2 = ToolResult(success=True)
        assert r1.data == {}
        assert r2.data == {}
        assert r1.data is not r2.data

    def test_frozen(self) -> None:
        """ToolResult is immutable."""
        result = ToolResult(success=True)
        with pytest.raises(AttributeError):
            result.success = False  # type: ignore[misc]

    def test_equality(self) -> None:
        """Two ToolResults with same fields are equal."""
        r1 = ToolResult(success=True, data={"a": 1})
        r2 = ToolResult(success=True, data={"a": 1})
        assert r1 == r2

    def test_repr(self) -> None:
        """ToolResult has a readable repr."""
        result = ToolResult(success=True, data={}, error=None)
        assert "ToolResult" in repr(result)
        assert "success=True" in repr(result)


class TestToolResultText:
    """Tests for the ToolResult.text field (pre-rendered output)."""

    def test_text_field_default(self) -> None:
        r = ToolResult(success=True)
        assert r.text is None

    def test_text_field_set(self) -> None:
        r = ToolResult(success=True, text="# Hi")
        assert r.text == "# Hi"

    def test_text_with_data(self) -> None:
        r = ToolResult(success=True, data={"k": 1}, text="k: 1")
        assert r.data == {"k": 1}
        assert r.text == "k: 1"

    def test_frozen_text(self) -> None:
        r = ToolResult(success=True, text="x")
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.text = "y"  # type: ignore[misc]

    def test_backward_compat(self) -> None:
        r = ToolResult(success=True, data={}, error=None, hint=None)
        assert r.text is None

    def test_text_empty_string(self) -> None:
        r = ToolResult(success=True, text="")
        assert r.text == ""
        assert r.text is not None

    def test_text_multiline_markdown(self) -> None:
        md = "| a | b |\n|---|---|\n| 1 | 2 |"
        r = ToolResult(success=True, text=md)
        assert r.text == md


# ── AXMTool ───────────────────────────────────────────────────────────────────


class ConcreteTool:
    """A concrete implementation for testing the protocol."""

    @property
    def name(self) -> str:
        return "test-tool"

    def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(success=True, data=kwargs)


class ExplicitParamTool:
    """A tool with explicit params (the preferred pattern)."""

    @property
    def name(self) -> str:
        return "explicit-tool"

    def execute(self, *, value: int = 0, label: str = "") -> ToolResult:
        return ToolResult(success=True, data={"value": value, "label": label})


class ToolWithHint:
    """A tool that provides an explicit agent_hint."""

    agent_hint = "Summarize data — use format param."

    @property
    def name(self) -> str:
        return "hint-tool"

    def execute(self, *, format: str = "json") -> ToolResult:
        return ToolResult(success=True, data={"format": format})


def test_concrete_tool_name() -> None:
    """Concrete tool returns its name."""
    tool = ConcreteTool()
    assert tool.name == "test-tool"


def test_concrete_tool_execute() -> None:
    """Concrete tool executes and returns a ToolResult."""
    tool = ConcreteTool()
    result = tool.execute(path="/tmp")
    assert result.success is True
    assert result.data == {"path": "/tmp"}


def test_explicit_param_tool() -> None:
    """Tool with explicit params satisfies the protocol."""
    tool = ExplicitParamTool()
    assert isinstance(tool, AXMTool)
    result = tool.execute(value=42, label="test")
    assert result.success is True
    assert result.data == {"value": 42, "label": "test"}


def test_tool_with_agent_hint() -> None:
    """Tool with explicit agent_hint satisfies the protocol."""
    tool = ToolWithHint()
    assert isinstance(tool, AXMTool)
    assert tool.agent_hint == "Summarize data — use format param."


def test_tool_without_agent_hint_isinstance() -> None:
    """Tool without agent_hint still satisfies the protocol."""
    # ConcreteTool has no agent_hint — isinstance must not require it
    tool = ConcreteTool()
    assert isinstance(tool, AXMTool)
    assert not hasattr(tool, "agent_hint")


def test_non_tool_fails_isinstance() -> None:
    """Object without name/execute is not an AXMTool."""

    class NotATool:
        pass

    assert not isinstance(NotATool(), AXMTool)


def test_all_exports() -> None:
    """__all__ contains the public surface."""
    from axm.tools import base

    assert "AXMTool" in base.__all__
    assert "ToolResult" in base.__all__
    assert "ToolMetadata" in base.__all__
    assert "tool_metadata" in base.__all__


def test_package_reexport() -> None:
    """axm.tools re-exports AXMTool and ToolResult."""
    from axm.tools import AXMTool as A
    from axm.tools import ToolResult as T

    assert A is AXMTool
    assert T is ToolResult


# ── ToolMetadata / tool_metadata ────────────────────────────────────────────────


class HotPathTool:
    """A tool opting into the MCP hot path with domain + tags."""

    expose_directly = True
    domain = "audit"
    tags = frozenset({"quality", "lint"})

    @property
    def name(self) -> str:
        return "hot-tool"

    def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(success=True)


class TestToolMetadata:
    """Tests for the ToolMetadata dataclass defaults and immutability."""

    def test_defaults(self) -> None:
        meta = ToolMetadata()
        assert meta.expose_directly is False
        assert meta.domain is None
        assert meta.tags == frozenset()

    def test_frozen(self) -> None:
        meta = ToolMetadata()
        with pytest.raises(dataclasses.FrozenInstanceError):
            meta.expose_directly = True  # type: ignore[misc]

    def test_default_tags_not_shared(self) -> None:
        # frozenset() is immutable, but assert the default resolves identically
        assert ToolMetadata().tags == ToolMetadata().tags


class TestToolMetadataReader:
    """Tests for tool_metadata() across subclass / structural / plain tools."""

    def test_reads_overridden_attributes(self) -> None:
        meta = tool_metadata(HotPathTool())
        assert meta.expose_directly is True
        assert meta.domain == "audit"
        assert meta.tags == frozenset({"quality", "lint"})

    def test_structural_tool_gets_defaults(self) -> None:
        # ConcreteTool declares none of the discovery attributes
        meta = tool_metadata(ConcreteTool())
        assert meta == ToolMetadata()

    def test_plain_callable_gets_defaults(self) -> None:
        def plain(**kwargs: Any) -> dict[str, Any]:
            return {}

        assert tool_metadata(plain) == ToolMetadata()

    def test_tags_list_is_coerced_to_frozenset(self) -> None:
        class ListTagsTool:
            tags: ClassVar[list[str]] = ["a", "b", "a"]

            @property
            def name(self) -> str:
                return "list-tags"

            def execute(self, **kwargs: Any) -> ToolResult:
                return ToolResult(success=True)

        assert tool_metadata(ListTagsTool()).tags == frozenset({"a", "b"})

    def test_none_tags_falls_back_to_empty(self) -> None:
        class NoneTagsTool:
            tags = None

            @property
            def name(self) -> str:
                return "none-tags"

            def execute(self, **kwargs: Any) -> ToolResult:
                return ToolResult(success=True)

        assert tool_metadata(NoneTagsTool()).tags == frozenset()


def test_discovery_attributes_do_not_break_structural_isinstance() -> None:
    """A structural tool without discovery attrs is still an AXMTool.

    Regression guard: the discovery attributes (expose_directly/domain/tags)
    must NOT be protocol members, otherwise runtime_checkable isinstance()
    would require them and break the many structural (non-subclass) tools.
    """
    tool = ConcreteTool()
    assert isinstance(tool, AXMTool)
    assert not hasattr(tool, "expose_directly")
    assert not hasattr(tool, "domain")
