"""Process-local operator origin; unknown and server origins are untrusted."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

__all__ = ["operator_authorized"]

_OPERATOR_TOOL: ContextVar[str | None] = ContextVar("axm_operator_tool", default=None)


def operator_authorized(tool_name: str) -> bool:
    """Return whether an interactive CLI explicitly launched this exact tool."""
    return bool(tool_name) and _OPERATOR_TOOL.get() == tool_name


@contextmanager
def _cli_operator_scope(tool_name: str) -> Iterator[None]:
    """Bind only the resolved CLI tool when standard input is a terminal."""
    selected = tool_name if sys.stdin.isatty() else None
    token = _OPERATOR_TOOL.set(selected)
    try:
        yield
    finally:
        _OPERATOR_TOOL.reset(token)


@contextmanager
def _untrusted_call_scope() -> Iterator[None]:
    """Discard inherited CLI authority while an MCP call is executing."""
    token = _OPERATOR_TOOL.set(None)
    try:
        yield
    finally:
        _OPERATOR_TOOL.reset(token)
