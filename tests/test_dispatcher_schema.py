"""Tests for dispatcher schema union.

Covers:
- _collect_dispatcher_params: builds union of sub-function signatures
- _register_one: dispatcher wrapper has correct __signature__
- End-to-end: wrapper forwards kwargs to sub-functions
"""

from __future__ import annotations

import inspect
import types
from typing import Any

from axm_mcp.discovery import _collect_dispatcher_params, _register_one

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

    # Bind to a fake module so _collect_dispatcher_params can find _ACTIONS
    mod = types.ModuleType("fake_dispatcher_mod")
    mod._FAKE_ACTIONS = actions  # type: ignore[attr-defined]
    dispatcher.__module__ = mod.__name__
    # Patch inspect.getmodule to return our fake module
    mod.dispatcher = dispatcher  # type: ignore[attr-defined]

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


# ──────────────── _collect_dispatcher_params tests ───────────────────


class TestCollectDispatcherParams:
    """_collect_dispatcher_params introspects sub-functions."""

    def test_returns_union_of_params(self) -> None:
        """Collects all params from sub-functions, deduped and optional."""
        dispatcher, _actions, mod = _make_dispatcher_module()

        params = _collect_dispatcher_params(dispatcher, override_module=mod)

        assert params is not None
        names = [p.name for p in params]
        # action is first, then sub-fn params sorted
        assert names[0] == "action"
        assert "path" in names
        assert "session_id" in names

    def test_all_union_params_are_optional(self) -> None:
        """All collected params (except action) have defaults."""
        dispatcher, _actions, mod = _make_dispatcher_module()

        params = _collect_dispatcher_params(dispatcher, override_module=mod)
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

        params = _collect_dispatcher_params(dispatcher, override_module=mod)
        assert params is not None

        name_counts: dict[str, int] = {}
        for p in params:
            name_counts[p.name] = name_counts.get(p.name, 0) + 1
        assert name_counts.get("session_id") == 1

    def test_returns_none_for_regular_function(self) -> None:
        """Regular function (no action + **kwargs) returns None."""

        def regular(*, path: str, limit: int = 5) -> dict[str, Any]:
            return {}

        result = _collect_dispatcher_params(regular)
        assert result is None

    def test_returns_none_without_actions_dict(self) -> None:
        """Dispatcher without _ACTIONS dict falls back to None."""

        def orphan_dispatcher(*, action: str, **kwargs: Any) -> dict[str, Any]:
            return {}

        # No module or no _ACTIONS dict → should return None
        result = _collect_dispatcher_params(orphan_dispatcher)
        assert result is None

    def test_sub_function_with_no_params(self) -> None:
        """sub_list() has no params — handled cleanly."""
        dispatcher, _actions, mod = _make_dispatcher_module()

        params = _collect_dispatcher_params(dispatcher, override_module=mod)
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
