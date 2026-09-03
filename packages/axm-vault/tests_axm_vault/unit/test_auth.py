"""Unit tests for value-less authentication dependencies."""

from __future__ import annotations

import importlib

import pytest


def _auth_module() -> object:
    return importlib.import_module("axm_vault.auth")


def test_connected_source_returns_connected_status() -> None:
    """AC3: a live-session declarer returns CONNECTED."""
    auth = _auth_module()

    class ConnectedSource:
        def status(self) -> object:
            return auth.AuthStatus.CONNECTED

    spec = auth.AuthDependencySpec(name="claude-session", source=ConnectedSource())

    assert spec.status() is auth.AuthStatus.CONNECTED


def test_status_preserves_three_distinct_states() -> None:
    """AC3: connected, disconnected, and tool-absent stay distinct."""
    auth = _auth_module()

    class StaticSource:
        def __init__(self, state: object) -> None:
            self._state = state

        def status(self) -> object:
            return self._state

    expected = (
        auth.AuthStatus.CONNECTED,
        auth.AuthStatus.DISCONNECTED,
        auth.AuthStatus.TOOL_ABSENT,
    )
    observed = tuple(
        auth.AuthDependencySpec(
            name=f"dependency-{index}", source=StaticSource(state)
        ).status()
        for index, state in enumerate(expected)
    )

    assert observed == expected
    assert len(set(observed)) == 3


def test_connected_dependency_exposes_no_value_accessor() -> None:
    """AC4: even a connected dependency exposes status, never a value."""
    auth = _auth_module()

    class ConnectedSource:
        def status(self) -> object:
            return auth.AuthStatus.CONNECTED

    spec = auth.AuthDependencySpec(name="claude-session", source=ConnectedSource())

    forbidden = {"resolve", "value", "secret", "get", "env_var"}
    assert forbidden.isdisjoint(name for name in dir(spec) if not name.startswith("_"))
    assert isinstance(spec.status(), auth.AuthStatus)


def test_non_auth_source_is_rejected() -> None:
    """AC5: construction rejects a declarer that is not an AuthSource."""
    auth = _auth_module()

    with pytest.raises(auth.UnsupportedAuthDeclarationError):
        auth.AuthDependencySpec(name="broken-session", source=object())
