"""Tests targeting uncovered code paths to push coverage from 80% to 95%+.

Covers:
- mcp_app.py: _verify_tool kwargs unwrap, main()
- discovery.py: _register_one wrapper execution/error, _register_list_tools
- __init__.py: main() entry point
- verify.py: _run_tool failure and exception paths
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

from axm_mcp.discovery import _register_list_tools, _register_one
from axm_mcp.verify import _run_tool

# ────────────────────────────── Helpers ──────────────────────────────


@dataclass
class FakeToolResult:
    """Minimal ToolResult stand-in."""

    success: bool = True
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class FakeTool:
    """Minimal ToolLike stand-in for testing registration."""

    def __init__(
        self,
        name: str = "fake_tool",
        *,
        result: FakeToolResult | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self._name = name
        self._result = result or FakeToolResult(data={"key": "val"})
        self._raise_exc = raise_exc

    @property
    def name(self) -> str:
        return self._name

    def execute(self, **kwargs: Any) -> FakeToolResult:
        """Execute the fake tool."""
        if self._raise_exc:
            raise self._raise_exc
        return self._result


class FakeMCP:
    """Minimal FastMCP stand-in that captures registered tools."""

    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self, *, name: str) -> Any:
        """Decorator that captures the wrapped function."""

        def decorator(fn: Any) -> Any:
            self.tools[name] = fn
            return fn

        return decorator


# ──────────────────────── mcp_app.py tests ───────────────────────────


class TestVerifyToolKwargs:
    """Cover _verify_tool kwargs unwrapping (mcp_app.py:38-41)."""

    def test_nested_kwargs_unwrap(self) -> None:
        """Nested kwargs={...} is unwrapped before delegation."""
        with patch("axm_mcp.mcp_app.verify_project") as mock_vp:
            mock_vp.return_value = {"audit": None, "governance": None}
            from axm_mcp.mcp_app import _verify_tool

            _verify_tool(kwargs={"path": "/tmp/proj"})
            # First positional arg should be the unwrapped path
            assert mock_vp.call_args[0][0] == "/tmp/proj"

    def test_flat_kwargs(self) -> None:
        """Flat kwargs are passed directly."""
        with patch("axm_mcp.mcp_app.verify_project") as mock_vp:
            mock_vp.return_value = {"audit": None, "governance": None}
            from axm_mcp.mcp_app import _verify_tool

            _verify_tool(path="/tmp/proj")
            assert mock_vp.call_args[0][0] == "/tmp/proj"


class TestMcpAppMain:
    """Cover main() in mcp_app.py (line 47)."""

    def test_main_calls_run(self) -> None:
        """main() delegates to mcp.run()."""
        with patch("axm_mcp.mcp_app.mcp") as mock_mcp:
            from axm_mcp.mcp_app import main

            main()
            mock_mcp.run.assert_called_once()


# ──────────────────────── __init__.py tests ──────────────────────────


class TestInitMain:
    """Cover main() in __init__.py (lines 10-12)."""

    def test_init_main_calls_run(self) -> None:
        """Package-level main() lazy-imports and runs the server."""
        with patch("axm_mcp.mcp_app.mcp") as mock_mcp:
            import axm_mcp

            axm_mcp.main()
            mock_mcp.run.assert_called_once()


# ──────────────────────── discovery.py tests ─────────────────────────


class TestRegisterOne:
    """Cover _register_one wrapper (discovery.py:91-97)."""

    def test_wrapper_returns_success(self) -> None:
        """Registered wrapper returns tool result as dict."""
        fake_mcp = FakeMCP()
        tool = FakeTool(result=FakeToolResult(success=True, data={"answer": 42}))
        _register_one(fake_mcp, "my_tool", tool)

        result = fake_mcp.tools["my_tool"]()
        assert result == {"success": True, "answer": 42}

    def test_wrapper_includes_error(self) -> None:
        """Wrapper includes error field when tool reports one."""
        fake_mcp = FakeMCP()
        tool = FakeTool(
            result=FakeToolResult(success=False, data={}, error="something broke"),
        )
        _register_one(fake_mcp, "err_tool", tool)

        result = fake_mcp.tools["err_tool"]()
        assert result["success"] is False
        assert result["error"] == "something broke"

    def test_wrapper_unwraps_nested_kwargs(self) -> None:
        """Wrapper unwraps kwargs={...} pattern from MCP."""
        fake_mcp = FakeMCP()
        tool = FakeTool(result=FakeToolResult(success=True, data={"ok": True}))
        _register_one(fake_mcp, "unwrap_tool", tool)

        result = fake_mcp.tools["unwrap_tool"](kwargs={"path": "/tmp"})
        assert result["success"] is True


class TestRegisterListTools:
    """Cover _register_list_tools inner fn (discovery.py:113-120)."""

    def test_lists_all_tools(self) -> None:
        """list_tools returns discovered + extra tools, sorted."""
        fake_mcp = FakeMCP()
        tools = {
            "beta_tool": FakeTool(name="beta_tool"),
            "alpha_tool": FakeTool(name="alpha_tool"),
        }
        extra = {"verify": "One-shot verify"}
        _register_list_tools(fake_mcp, tools, extra)

        result = fake_mcp.tools["list_tools"]()
        assert result["count"] == 3
        names = [t["name"] for t in result["tools"]]
        assert names == ["alpha_tool", "beta_tool", "verify"]


# ──────────────────────── verify.py tests ────────────────────────────


class TestRunToolErrorPaths:
    """Cover _run_tool failure/exception (verify.py:68-72)."""

    def test_tool_failure_returns_error(self) -> None:
        """When tool.execute returns success=False, return error dict."""
        tool = FakeTool(
            result=FakeToolResult(success=False, error="audit failed"),
        )
        result = _run_tool({"audit": tool}, "audit", path=".")
        assert result == {"error": "audit failed"}

    def test_tool_exception_returns_error(self) -> None:
        """When tool.execute raises, catch and return error dict."""
        tool = FakeTool(raise_exc=RuntimeError("boom"))
        result = _run_tool({"audit": tool}, "audit", path=".")
        assert result is not None
        assert "boom" in result["error"]
