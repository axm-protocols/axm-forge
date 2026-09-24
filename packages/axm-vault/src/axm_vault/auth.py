from __future__ import annotations

from enum import StrEnum
from typing import Protocol, Self, runtime_checkable

from pydantic import BaseModel, ConfigDict, PrivateAttr, model_validator

__all__ = [
    "AuthDependencySpec",
    "AuthSource",
    "AuthStatus",
    "UnsupportedAuthDeclarationError",
]


class AuthStatus(StrEnum):
    """Observed state of an authentication dependency."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    TOOL_ABSENT = "tool_absent"


@runtime_checkable
class AuthSource(Protocol):
    """Capability supplied by packages declaring an authentication dependency."""

    def status(self) -> AuthStatus:
        """Observe the dependency without reading authentication material."""
        ...


class UnsupportedAuthDeclarationError(RuntimeError):
    """Raised when an authentication declarer does not implement AuthSource."""


class AuthDependencySpec(BaseModel):  # type: ignore[explicit-any]
    """A value-less authentication dependency and its state source."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )

    name: str
    login_command: str
    """Command a human runs to restore the authenticated session."""
    _source: AuthSource = PrivateAttr()

    def __init__(self, *, name: str, source: object, **data: object) -> None:
        if not isinstance(source, AuthSource):
            raise UnsupportedAuthDeclarationError(
                f"authentication dependency {name!r} has no valid AuthSource"
            )
        super().__init__(name=name, **data)
        self._source = source

    def status(self) -> AuthStatus:
        """Return the source's current tri-state authentication status."""
        return self._source.status()

    @model_validator(mode="after")
    def _require_login_command(self) -> Self:
        # A model validator (not a field validator) so that it still runs when
        # a subclass redeclares ``login_command``.
        if not self.login_command.strip():
            msg = (
                f"authentication dependency {self.name!r} must declare a "
                "non-empty login_command"
            )
            raise ValueError(msg)
        return self
