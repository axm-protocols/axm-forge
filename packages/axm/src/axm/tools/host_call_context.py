"""Request-local evidence for a trusted host adapter.

Transport evidence is not itself authority: consumers must authenticate the
client and bind its operator-configured scope before using any identity.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class HostCallContext:
    """Evidence for exactly one tool call, kept out of model arguments."""

    target: str
    client_token: str = field(default="", repr=False)
    thread_id: str = field(default="", repr=False)
    turn_id: str = field(default="", repr=False)
    call_id: str = field(default="", repr=False)
    thread_type: str = "absent"
    turn_type: str = "absent"
    call_type: str = "absent"


_CONTEXT: ContextVar[HostCallContext | None] = ContextVar("axm_host_call", default=None)


def current_host_call(target: str) -> HostCallContext | None:
    """Return evidence only for the exact target selected by the transport."""
    value = _CONTEXT.get()
    return value if value is not None and value.target == target else None


@contextmanager
def bind_host_call(value: HostCallContext) -> Iterator[None]:
    """Bind trusted-transport evidence for one request and always reset it."""
    token = _CONTEXT.set(value)
    try:
        yield
    finally:
        _CONTEXT.reset(token)


__all__ = ["HostCallContext", "bind_host_call", "current_host_call"]
