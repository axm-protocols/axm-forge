"""Positive tool scopes for nested name-based discovery and invocation."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from functools import wraps
from typing import TYPE_CHECKING, cast

from axm.tools.dependency_reads import (
    current_read_contract,
    read_context_bound,
    restricted_read_context,
)

if TYPE_CHECKING:
    from axm.tools.base import AXMTool, ToolResult

__all__ = [
    "ToolAccessDenied",
    "check_tool_execution",
    "guard_tool",
    "has_tool_execution_guard",
    "require_tool_access",
    "tool_access_scope",
    "tool_execution_guard",
    "tool_is_allowed",
]

type ExecutionGuard = Callable[[str, dict[str, object], object], None]
_GUARDS: ContextVar[tuple[ExecutionGuard, ...]] = ContextVar(
    "axm_tool_execution_guards", default=()
)


def has_tool_execution_guard() -> bool:
    """Whether execution needs a host policy check (and a worker thread)."""
    return bool(_GUARDS.get())


def check_tool_execution(name: str, kwargs: dict[str, object], execute: object) -> None:
    """Revalidate all live execution guards immediately before an effect."""
    require_tool_access(name)
    for guard in _GUARDS.get():
        guard(name, kwargs, execute)


@contextmanager
def tool_execution_guard(guard: ExecutionGuard) -> Iterator[None]:
    """Install a neutral execution guard; inner scopes cannot remove outer guards.

    Guards validate the current lease and may normalize detached keyword args.
    They run immediately before execution, including cached and injected tools.
    A transport owns its callback: the SDK does not import the transport.
    """
    token = _GUARDS.set((*_GUARDS.get(), guard))
    try:
        yield
    finally:
        _GUARDS.reset(token)


def guard_tool(name: str, tool: AXMTool) -> AXMTool:
    """Retain execution authority around a resolved tool without changing metadata.

    Legacy resolution returns the original object. A scoped handle retains its
    guards even if cached and subsequently invoked outside the creating block.
    """
    guards = _GUARDS.get()
    allowed = _ALLOWED.get()
    if not guards and allowed is None:
        return tool

    original = tool.execute
    origin_contract = current_read_contract()
    origin_bound = read_context_bound() or origin_contract is not None

    @wraps(original)
    def execute(**kwargs: object) -> ToolResult:
        require_tool_access(name)
        if allowed is not None and name not in allowed:
            raise ToolAccessDenied(f"undeclared tool refused: {name}")
        combined = (*guards, *_GUARDS.get())
        for index, guard in enumerate(combined):
            if any(guard is previous for previous in combined[:index]):
                continue
            guard(name, kwargs, original)
        authority = (
            restricted_read_context(origin_contract) if origin_bound else nullcontext()
        )
        with authority:
            return original(**kwargs)

    class GuardedTool:
        def __getattr__(self, key: str) -> object:
            return getattr(tool, key)

    guarded = GuardedTool()
    guarded.execute = execute  # type: ignore[attr-defined]
    return cast("AXMTool", guarded)


_ALLOWED: ContextVar[frozenset[str] | None] = ContextVar(
    "axm_allowed_tools", default=None
)


class ToolAccessDenied(PermissionError):  # noqa: N818
    """A named dispatch attempted to escape its positive tool scope."""


def tool_is_allowed(name: str) -> bool:
    """Whether a canonical name belongs to the current tool scope."""
    allowed = _ALLOWED.get()
    return allowed is None or name in allowed


def require_tool_access(name: str) -> None:
    """Recheck resolutions, including cached nodes and injected overrides."""
    if not tool_is_allowed(name):
        raise ToolAccessDenied(f"undeclared tool refused: {name}")


@contextmanager
def tool_access_scope(names: frozenset[str]) -> Iterator[None]:
    """Apply an immutable allowlist; nested scopes can only narrow it."""
    if not isinstance(names, frozenset):
        raise ValueError("tool scope must be an immutable frozenset")
    outer = _ALLOWED.get()
    token = _ALLOWED.set(names if outer is None else outer & names)
    try:
        yield
    finally:
        _ALLOWED.reset(token)
