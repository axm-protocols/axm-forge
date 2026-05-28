"""Tests for dispatcher schema union.

Covers:
- collect_dispatcher_params: builds union of sub-function signatures
- _register_one: dispatcher wrapper has correct __signature__
- End-to-end: wrapper forwards kwargs to sub-functions
"""

from __future__ import annotations

import inspect
import types
from typing import Any

from axm_mcp.discovery import _register_one
from axm_mcp.schema import collect_dispatcher_params, extract_docstring_params

# ────────────────────────────── Fixtures ─────────────────────────────────


def _make_dispatcher_module() -> tuple[Any, dict[str, Any], types.ModuleType]:
    """Create a fake module with a dispatcher + _ACTIONS dict.

    Returns:
        (dispatcher_fn, actions_dict, module) — the dispatcher is bound to the module.
    """

    def sub_open(*, path: str) -> dict[str, Any]:
        """Open something."""
        return {"path": path}

    def sub_save(*, session_id: str) -> dict[str, Any]:
        """Save something."""
        return {"session_id": session_id}

    def sub_save_as(*, session_id: str, path: str) -> dict[str, Any]:
        """Save to a new path."""
        return {"session_id": session_id, "path": path}

    def sub_list() -> dict[str, Any]:
        """List all — no params."""
        return {"items": []}

    actions: dict[str, Any] = {
        "open": sub_open,
        "save": sub_save,
        "save_as": sub_save_as,
        "list": sub_list,
    }

    def dispatcher(*, action: str, **kwargs: Any) -> dict[str, Any]:
        """Fake dispatcher.

        Actions: open, save, save_as, list.

        Args:
            action: The operation to perform.
            **kwargs: Arguments forwarded to the action function.
        """
        fn = actions[action]
        result: dict[str, Any] = fn(**kwargs)
        return result

    # Bind to a fake module so collect_dispatcher_params can find _ACTIONS
    mod = types.ModuleType("fake_dispatcher_mod")
    mod._FAKE_ACTIONS = actions
    dispatcher.__module__ = mod.__name__
    # Patch inspect.getmodule to return our fake module
    mod.dispatcher = dispatcher

    return dispatcher, actions, mod


class FakeMCP:
    """Minimal FastMCP stand-in that captures registered tools."""

    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self, *, name: str) -> Any:
        def decorator(fn: Any) -> Any:
            self.tools[name] = fn
            return fn

        return decorator


# ──────────────── collect_dispatcher_params tests ───────────────────


class TestCollectDispatcherParams:
    """collect_dispatcher_params introspects sub-functions."""

    def test_returns_union_of_params(self) -> None:
        """Collects all params from sub-functions, deduped and optional."""
        dispatcher, _actions, mod = _make_dispatcher_module()

        params = collect_dispatcher_params(dispatcher, override_module=mod)

        assert params is not None
        names = [p.name for p in params]
        # action is first, then sub-fn params sorted
        assert names[0] == "action"
        assert "path" in names
        assert "session_id" in names

    def test_all_union_params_are_optional(self) -> None:
        """All collected params (except action) have defaults."""
        dispatcher, _actions, mod = _make_dispatcher_module()

        params = collect_dispatcher_params(dispatcher, override_module=mod)
        assert params is not None

        for p in params:
            if p.name == "action":
                continue
            assert p.default is not inspect.Parameter.empty, (
                f"Param '{p.name}' should have a default"
            )

    def test_deduplicates_overlapping_params(self) -> None:
        """session_id appears in save AND save_as — only once in union."""
        dispatcher, _actions, mod = _make_dispatcher_module()

        params = collect_dispatcher_params(dispatcher, override_module=mod)
        assert params is not None

        name_counts: dict[str, int] = {}
        for p in params:
            name_counts[p.name] = name_counts.get(p.name, 0) + 1
        assert name_counts.get("session_id") == 1

    def test_returns_none_for_regular_function(self) -> None:
        """Regular function (no action + **kwargs) returns None."""

        def regular(*, path: str, limit: int = 5) -> dict[str, Any]:
            return {}

        result = collect_dispatcher_params(regular)
        assert result is None

    def test_returns_none_without_actions_dict(self) -> None:
        """Dispatcher without _ACTIONS dict falls back to None."""

        def orphan_dispatcher(*, action: str, **kwargs: Any) -> dict[str, Any]:
            return {}

        # No module or no _ACTIONS dict → should return None
        result = collect_dispatcher_params(orphan_dispatcher)
        assert result is None

    def test_sub_function_with_no_params(self) -> None:
        """sub_list() has no params — handled cleanly."""
        dispatcher, _actions, mod = _make_dispatcher_module()

        params = collect_dispatcher_params(dispatcher, override_module=mod)
        # Should not crash and should still collect other params
        assert params is not None
        assert len(params) >= 2  # at least action + path


# ─────────────── Registration + forwarding tests ────────────────────


class TestDispatcherRegistration:
    """_register_one creates correct schema for dispatchers."""

    def test_registered_wrapper_has_union_signature(self) -> None:
        """Wrapper __signature__ includes action + all sub-fn params."""
        dispatcher, _actions, mod = _make_dispatcher_module()
        fake_mcp = FakeMCP()

        _register_one(fake_mcp, "test_dispatch", dispatcher, override_module=mod)

        wrapper = fake_mcp.tools["test_dispatch"]
        sig = inspect.signature(wrapper)
        param_names = list(sig.parameters.keys())

        assert "action" in param_names
        assert "path" in param_names
        assert "session_id" in param_names

    def test_wrapper_forwards_kwargs_to_subfn(self) -> None:
        """Calling wrapper(action='open', path='/x') reaches sub_open."""
        dispatcher, _actions, mod = _make_dispatcher_module()
        fake_mcp = FakeMCP()

        _register_one(fake_mcp, "test_dispatch", dispatcher, override_module=mod)

        result = fake_mcp.tools["test_dispatch"](action="open", path="/tmp/test")
        assert result == {"path": "/tmp/test"}

    def test_wrapper_handles_no_kwargs_action(self) -> None:
        """Calling wrapper(action='list') works with sub-fn that has no params."""
        dispatcher, _actions, mod = _make_dispatcher_module()
        fake_mcp = FakeMCP()

        _register_one(fake_mcp, "test_dispatch", dispatcher, override_module=mod)

        result = fake_mcp.tools["test_dispatch"](action="list")
        assert result == {"items": []}


# ─────────── extract_docstring_params tests ─────────────────────────


class TestExtractDocstringParams:
    """extract_docstring_params parses Google-style Args sections."""

    def test_parses_typed_params(self) -> None:
        """Extracts params with type annotations."""
        doc = """\
        Do something.

        Args:
            path (str): Path to directory.
            name (str): Project name.
            limit (int): Max results.
        """
        params = extract_docstring_params(doc)
        names = [p.name for p in params]
        assert names == ["path", "name", "limit"]
        assert params[0].annotation is str
        assert params[2].annotation is int

    def test_parses_untyped_params(self) -> None:
        """Extracts params without type annotations."""
        doc = """\
        Do something.

        Args:
            path: Path to directory.
            verbose: Enable verbose mode.
        """
        params = extract_docstring_params(doc)
        assert len(params) == 2
        assert params[0].name == "path"
        assert params[0].annotation is inspect.Parameter.empty

    def test_returns_empty_for_no_args(self) -> None:
        """No Args section → empty list."""
        doc = """Do something simple."""
        params = extract_docstring_params(doc)
        assert params == []

    def test_returns_empty_for_none(self) -> None:
        """None docstring → empty list."""
        params = extract_docstring_params(None)
        assert params == []

    def test_skips_kwargs(self) -> None:
        """**kwargs line is ignored."""
        doc = """\
        Do something.

        Args:
            path (str): Path to dir.
            **kwargs: Extra arguments.
        """
        params = extract_docstring_params(doc)
        assert len(params) == 1
        assert params[0].name == "path"

    def test_stops_at_returns_section(self) -> None:
        """Args: block ends at Returns: section."""
        doc = """\
        Do something.

        Args:
            path (str): Path to directory.

        Returns:
            ToolResult with data.
        """
        params = extract_docstring_params(doc)
        assert len(params) == 1
        assert params[0].name == "path"

    def test_all_params_are_keyword_only(self) -> None:
        """All extracted params are KEYWORD_ONLY with default=None."""
        doc = """\
        Do something.

        Args:
            path (str): Path.
            limit (int): Max.
        """
        params = extract_docstring_params(doc)
        for p in params:
            assert p.kind == inspect.Parameter.KEYWORD_ONLY
            assert p.default is None

    def test_handles_optional_type_suffix(self) -> None:
        """Type with ', optional' suffix is cleaned."""
        doc = """\
        Do something.

        Args:
            path (str, optional): Optional path.
        """
        params = extract_docstring_params(doc)
        assert params[0].annotation is str


# ─────────── Non-dispatcher (AXMTool) registration ───────────────────


class TestNonDispatcherRegistration:
    """_register_one uses docstring fallback for AXMTool.execute(**kwargs)."""

    def test_axm_tool_with_kwargs_gets_docstring_params(self) -> None:
        """AXMTool.execute(**kwargs) exposes params from docstring."""

        class FakeTool:
            @property
            def name(self) -> str:
                return "test_tool"

            def execute(self, **kwargs: Any) -> Any:
                """Do something.

                Args:
                    path (str): Path to directory.
                    name (str): Project name.

                Returns:
                    ToolResult with data.
                """

                class _R:
                    success = True
                    data = kwargs
                    error = None

                return _R()

        fake_mcp = FakeMCP()
        tool = FakeTool()
        _register_one(fake_mcp, "test_tool", tool)

        wrapper = fake_mcp.tools["test_tool"]
        sig = inspect.signature(wrapper)
        param_names = list(sig.parameters.keys())

        assert "path" in param_names
        assert "name" in param_names

    def test_axm_tool_without_docstring_has_no_params(self) -> None:
        """AXMTool.execute(**kwargs) without docstring → empty params."""

        class BareTool:
            @property
            def name(self) -> str:
                return "bare"

            def execute(self, **kwargs: Any) -> Any:
                class _R:
                    success = True
                    data: dict[str, Any] = {}
                    error = None

                return _R()

        fake_mcp = FakeMCP()
        _register_one(fake_mcp, "bare", BareTool())

        wrapper = fake_mcp.tools["bare"]
        sig = inspect.signature(wrapper)
        assert len(sig.parameters) == 0

    def test_regular_tool_with_typed_params_not_affected(self) -> None:
        """Tool with typed execute(self, *, path: str) keeps normal params."""

        class TypedTool:
            @property
            def name(self) -> str:
                return "typed"

            def execute(self, *, path: str, limit: int = 5) -> Any:
                """Do something.

                Args:
                    path: Path to directory.
                    limit: Max results.
                """

                class _R:
                    success = True
                    data = {"path": path, "limit": limit}
                    error = None

                return _R()

        fake_mcp = FakeMCP()
        _register_one(fake_mcp, "typed", TypedTool())

        wrapper = fake_mcp.tools["typed"]
        sig = inspect.signature(wrapper)
        param_names = list(sig.parameters.keys())

        # Normal introspection should work — params come from signature, not docstring
        assert "path" in param_names
        assert "limit" in param_names
