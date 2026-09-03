from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, PrivateAttr

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
