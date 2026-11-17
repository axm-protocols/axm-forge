"""Extract narrowly scoped MCP transport evidence for host agent tools."""

from __future__ import annotations

import json
from collections.abc import Mapping
from contextlib import AbstractContextManager, nullcontext
from typing import Protocol, cast

from axm.tools.host_call_context import HostCallContext, bind_host_call

_TARGETS = frozenset(
    {
        "agent_context",
        "agent_spawn",
        "agent_status",
        "agent_events",
        "agent_result",
        "agent_cancel",
        "agent_close",
        "agent_next_turn",
        "agent_wait",
        "agent_resume",
    }
)


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        result = dump(by_alias=True)
        if isinstance(result, Mapping):
            return result
    return {}


def _field(value: object) -> tuple[str, str]:
    if value is None:
        return "", "absent"
    if isinstance(value, str):
        return value, "str"
    return "", type(value).__name__


class _Context(Protocol):
    @property
    def request_context(self) -> object: ...


def _turn_value(value: object) -> str | None:
    if not isinstance(value, Mapping):
        return None
    turn = value.get("turn_id")
    return turn if isinstance(turn, str) and turn else None


def _turn_header(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return _turn_value(json.loads(value))
    except (ValueError, TypeError):
        return None


def _turn_id(meta: Mapping[str, object], headers: Mapping[str, object]) -> str | None:
    """Prefer native MCP metadata; conflicting or malformed evidence fails closed."""
    key = "x-codex-turn-metadata"
    native = _turn_value(meta[key]) if key in meta else None
    legacy = _turn_header(headers[key]) if key in headers else None
    if (key in meta and native is None) or (key in headers and legacy is None):
        return None
    if native is not None and legacy is not None and native != legacy:
        return None
    return native if native is not None else legacy


def _evidence(target: str, context: object | None) -> HostCallContext:
    try:
        request_context = cast(_Context, context).request_context
    except (AttributeError, ValueError):
        return HostCallContext(target)
    meta = _mapping(getattr(request_context, "meta", None))
    request = getattr(request_context, "request", None)
    headers = getattr(request, "headers", {})
    if not isinstance(headers, Mapping):
        headers = {}
    turn = _turn_id(meta, headers)
    thread, thread_type = _field(meta.get("threadId"))
    call, call_type = _field(meta.get("codex_bridge_mcp_call_id"))
    turn_id, turn_type = _field(turn)
    token = headers.get("x-axm-host-token", "")
    return HostCallContext(
        target=target,
        client_token=token if isinstance(token, str) else "",
        thread_id=thread,
        turn_id=turn_id,
        call_id=call,
        thread_type=thread_type,
        turn_type=turn_type,
        call_type=call_type,
    )


def transport_host_call(
    name: str, arguments: Mapping[str, object], context: object | None
) -> AbstractContextManager[None]:
    """Bind evidence only for the effective, exact host-agent target."""
    target = arguments.get("name") if name == "axm_call" else name
    if not isinstance(target, str) or target not in _TARGETS:
        return nullcontext()
    return bind_host_call(_evidence(target, context))


__all__ = ["transport_host_call"]
