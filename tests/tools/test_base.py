"""Tests for AXMTool and ToolResult shared interface."""

from __future__ import annotations

from typing import Any

import pytest

from axm.tools.base import AXMTool, ToolResult

# ── ToolResult ────────────────────────────────────────────────────────────────


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


class TestAXMTool:
    """Tests for the AXMTool structural protocol."""

    def test_concrete_tool_name(self) -> None:
        """Concrete tool returns its name."""
        tool = ConcreteTool()
        assert tool.name == "test-tool"

    def test_concrete_tool_execute(self) -> None:
        """Concrete tool executes and returns a ToolResult."""
        tool = ConcreteTool()
        result = tool.execute(path="/tmp")
        assert result.success is True
        assert result.data == {"path": "/tmp"}

    def test_isinstance_check(self) -> None:
        """runtime_checkable Protocol supports isinstance()."""
        tool = ConcreteTool()
        assert isinstance(tool, AXMTool)

    def test_explicit_param_tool(self) -> None:
        """Tool with explicit params satisfies the protocol."""
        tool = ExplicitParamTool()
        assert isinstance(tool, AXMTool)
        result = tool.execute(value=42, label="test")
        assert result.success is True
        assert result.data == {"value": 42, "label": "test"}

    def test_non_tool_fails_isinstance(self) -> None:
        """Object without name/execute is not an AXMTool."""

        class NotATool:
            pass

        assert not isinstance(NotATool(), AXMTool)


# ── Exports ───────────────────────────────────────────────────────────────────


class TestExports:
    """Test that the public API is correctly exported."""

    def test_all_exports(self) -> None:
        """__all__ contains AXMTool and ToolResult."""
        from axm.tools import base

        assert "AXMTool" in base.__all__
        assert "ToolResult" in base.__all__

    def test_package_reexport(self) -> None:
        """axm.tools re-exports AXMTool and ToolResult."""
        from axm.tools import AXMTool as A
        from axm.tools import ToolResult as T

        assert A is AXMTool
        assert T is ToolResult
