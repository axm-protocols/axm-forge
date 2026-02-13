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
            result.success = False

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


class ConcreteTool(AXMTool):  # type: ignore[misc]
    """A concrete implementation for testing the ABC."""

    @property
    def name(self) -> str:
        return "test-tool"

    def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(success=True, data=kwargs)


class TestAXMTool:
    """Tests for the AXMTool abstract base class."""

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

    def test_cannot_instantiate_abc(self) -> None:
        """AXMTool cannot be instantiated directly."""
        with pytest.raises(TypeError):
            AXMTool()

    def test_must_implement_name(self) -> None:
        """Subclass without name raises TypeError."""

        class NoName(AXMTool):  # type: ignore[misc]
            def execute(self, **kwargs: Any) -> ToolResult:
                return ToolResult(success=True)

        with pytest.raises(TypeError):
            NoName()

    def test_must_implement_execute(self) -> None:
        """Subclass without execute raises TypeError."""

        class NoExecute(AXMTool):  # type: ignore[misc]
            @property
            def name(self) -> str:
                return "no-exec"

        with pytest.raises(TypeError):
            NoExecute()


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
