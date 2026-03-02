"""Tests for HookResult and HookAction shared interface."""

from __future__ import annotations

from typing import Any

import pytest

from axm.hooks.base import HookAction, HookResult

# ── HookResult ────────────────────────────────────────────────────────────────


class TestHookResult:
    """Tests for the HookResult dataclass."""

    def test_ok_factory(self) -> None:
        """HookResult.ok() creates a successful result with metadata."""
        result = HookResult.ok(key="val")
        assert result.success is True
        assert result.metadata == {"key": "val"}
        assert result.error is None

    def test_fail_factory(self) -> None:
        """HookResult.fail() creates a failed result with error."""
        result = HookResult.fail("err")
        assert result.success is False
        assert result.error == "err"

    def test_frozen(self) -> None:
        """HookResult is immutable."""
        result = HookResult.ok()
        with pytest.raises(AttributeError):
            result.success = False  # type: ignore[misc]

    def test_default_metadata_is_empty_dict(self) -> None:
        """Default metadata is an empty dict, not shared across instances."""
        r1 = HookResult(success=True)
        r2 = HookResult(success=True)
        assert r1.metadata == {}
        assert r2.metadata == {}
        assert r1.metadata is not r2.metadata

    def test_equality(self) -> None:
        """Two HookResults with same fields are equal."""
        r1 = HookResult.ok(a=1)
        r2 = HookResult.ok(a=1)
        assert r1 == r2


# ── HookAction ────────────────────────────────────────────────────────────────


class TestHookAction:
    """Tests for the HookAction structural protocol."""

    def test_isinstance_check(self) -> None:
        """A concrete class with execute(context, **params) satisfies the protocol."""

        class ConcreteHook:
            def execute(self, context: dict[str, Any], **params: Any) -> HookResult:
                return HookResult.ok(**params)

        assert isinstance(ConcreteHook(), HookAction)

    def test_non_hook_fails_isinstance(self) -> None:
        """Object without execute is not a HookAction."""

        class NotAHook:
            pass

        assert not isinstance(NotAHook(), HookAction)


# ── Exports ───────────────────────────────────────────────────────────────────


class TestExports:
    """Test that the public API is correctly exported."""

    def test_all_exports(self) -> None:
        """__all__ contains HookAction and HookResult."""
        from axm.hooks import base

        assert "HookAction" in base.__all__
        assert "HookResult" in base.__all__

    def test_package_reexport(self) -> None:
        """axm.hooks re-exports HookAction and HookResult."""
        from axm.hooks import HookAction as A
        from axm.hooks import HookResult as R

        assert A is HookAction
        assert R is HookResult
