"""Unit tests for value-less authentication dependencies."""

from __future__ import annotations

import importlib

import pydantic
import pytest

from axm_vault.auth import AuthDependencySpec


def _auth_module() -> object:
    return importlib.import_module("axm_vault.auth")


class _ConnectedSource:
    """Test-local AuthSource whose status is always CONNECTED."""

    def status(self) -> object:
        return _auth_module().AuthStatus.CONNECTED


class _CliShapedDependency(AuthDependencySpec):
    """CliSessionCredential-shaped subclass redeclaring ``login_command: str``."""

    login_command: str
    binary: str
    session_file: str
    keychain_service: str

    def __init__(self, *, source: object, **data: object) -> None:
        super().__init__(source=source, **data)


def test_connected_source_returns_connected_status() -> None:
    """AC3: a live-session declarer returns CONNECTED."""
    auth = _auth_module()

    class ConnectedSource:
        def status(self) -> object:
            return auth.AuthStatus.CONNECTED

    spec = auth.AuthDependencySpec(
        name="claude-session",
        source=ConnectedSource(),
        login_command="claude login",
    )

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
            name=f"dependency-{index}",
            source=StaticSource(state),
            login_command="tool login",
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

    spec = auth.AuthDependencySpec(
        name="claude-session",
        source=ConnectedSource(),
        login_command="claude login",
    )

    forbidden = {"resolve", "value", "secret", "get", "env_var"}
    assert forbidden.isdisjoint(name for name in dir(spec) if not name.startswith("_"))
    assert isinstance(spec.status(), auth.AuthStatus)


def test_non_auth_source_is_rejected() -> None:
    """AC5: construction rejects a declarer that is not an AuthSource."""
    auth = _auth_module()

    with pytest.raises(auth.UnsupportedAuthDeclarationError):
        auth.AuthDependencySpec(name="broken-session", source=object())


def test_undeclared_field_is_rejected() -> None:
    """G1: with a valid login command, an unknown field alone is refused."""
    auth = _auth_module()

    class ConnectedSource:
        def status(self) -> object:
            return auth.AuthStatus.CONNECTED

    with pytest.raises(pydantic.ValidationError) as excinfo:
        auth.AuthDependencySpec(
            name="claude-session",
            source=ConnectedSource(),
            login_command="x login",
            token="secret",
        )

    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]["type"] == "extra_forbidden"
    assert errors[0]["loc"] == ("token",)


def test_cli_shaped_subclass_redeclaring_login_command_is_accepted() -> None:
    """AC2: accept a CLI-shaped redeclaration and the base login contract."""
    auth = _auth_module()

    class ConnectedSource:
        def status(self) -> object:
            return auth.AuthStatus.CONNECTED

    class CliShapedDependency(AuthDependencySpec):
        login_command: str
        binary: str
        session_file: str
        keychain_service: str

        def __init__(self, *, source: object, **data: object) -> None:
            super().__init__(source=source, **data)

    dependency = CliShapedDependency(
        name="claude-session",
        source=ConnectedSource(),
        login_command="claude login",
        binary="claude",
        session_file="~/.claude/session",
        keychain_service="claude",
    )
    assert dependency.login_command == "claude login"


def test_gh_shaped_subclass_redeclaring_status_command_is_accepted() -> None:
    """AC3: keep GH status and login commands distinct under the base contract."""
    auth = _auth_module()

    class ConnectedSource:
        def status(self) -> object:
            return auth.AuthStatus.CONNECTED

    class GhShapedDependency(AuthDependencySpec):
        package: str
        status_command: str
        login_command: str

        def __init__(self, *, source: object, **data: object) -> None:
            super().__init__(source=source, **data)

    dependency = GhShapedDependency(
        name="gh",
        source=ConnectedSource(),
        package="axm-git",
        status_command="gh auth status",
        login_command="gh auth login",
    )
    assert dependency.status_command == "gh auth status"
    assert dependency.login_command == "gh auth login"


def test_base_dependency_accepts_and_exposes_login_command() -> None:
    """AC1: the base contract accepts and exposes a login command."""
    auth = _auth_module()

    class ConnectedSource:
        def status(self) -> object:
            return auth.AuthStatus.CONNECTED

    spec = auth.AuthDependencySpec(
        name="claude-session",
        source=ConnectedSource(),
        login_command="claude login",
    )

    assert spec.login_command == "claude login"


def test_base_dependency_declares_login_command_field() -> None:
    """AC2: login_command is declared by the base model contract."""
    auth = _auth_module()

    assert "login_command" in auth.AuthDependencySpec.model_fields


def test_base_dependency_without_login_command_is_rejected() -> None:
    """AC1: a declaration omitting login_command fails validation."""
    auth = _auth_module()

    with pytest.raises(pydantic.ValidationError):
        auth.AuthDependencySpec(name="x", source=_ConnectedSource())


@pytest.mark.parametrize("blank", ["", "   "], ids=["empty", "spaces"])
def test_base_dependency_rejects_blank_login_command(blank: str) -> None:
    """AC2, AC3: an empty or whitespace-only login_command fails validation."""
    auth = _auth_module()

    with pytest.raises(pydantic.ValidationError):
        auth.AuthDependencySpec(
            name="x", source=_ConnectedSource(), login_command=blank
        )


def test_base_dependency_rejects_none_login_command() -> None:
    """AC4: an explicit ``login_command=None`` fails validation."""
    auth = _auth_module()

    with pytest.raises(pydantic.ValidationError):
        auth.AuthDependencySpec(name="x", source=_ConnectedSource(), login_command=None)


@pytest.mark.parametrize("blank", ["", "   "], ids=["empty", "spaces"])
def test_cli_shaped_subclass_rejects_blank_login_command(blank: str) -> None:
    """AC5, AC6: a subclass redeclaring ``login_command: str`` still refuses blanks."""
    with pytest.raises(pydantic.ValidationError):
        _CliShapedDependency(
            name="x",
            source=_ConnectedSource(),
            login_command=blank,
            binary="claude",
            session_file="~/.claude/session",
            keychain_service="claude",
        )
