from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from typing import TypedDict, cast

from axm.tools.write_scope import WriteContract
from pydantic import TypeAdapter, ValidationError

__all__ = [
    "SessionContractRegistry",
    "UnboundSessionError",
    "WriteContract",
    "WriteContractHeaderError",
    "parse_write_contract_header",
]


class UnboundSessionError(RuntimeError):
    """Raised when no write contract is bound to a session."""


class _WriteContractPayload(TypedDict):
    execution_root: str
    allowed_prefixes: list[str]
    markdown_only_prefixes: list[str]


_WRITE_CONTRACT_ADAPTER = TypeAdapter(_WriteContractPayload)


class WriteContractHeaderError(ValueError):
    """Raised when the X-AXM-Write-Contract header cannot be decoded."""


def parse_write_contract_header(raw: str) -> WriteContract:
    """Decode and validate an X-AXM-Write-Contract header value."""
    try:
        payload = _WRITE_CONTRACT_ADAPTER.validate_json(raw)
    except ValidationError as exc:
        raise WriteContractHeaderError(
            f"invalid X-AXM-Write-Contract header: {exc}"
        ) from exc
    return WriteContract(
        execution_root=payload["execution_root"],
        allowed_prefixes=cast("tuple[str, ...]", payload["allowed_prefixes"]),
        markdown_only_prefixes=cast(
            "tuple[str, ...]", payload["markdown_only_prefixes"]
        ),
    )


class SessionContractRegistry:
    """Thread-safe registry of write contracts keyed by session identity."""

    def __init__(
        self,
        *,
        clock: Callable[[], float],
        ttl_seconds: float = 3_600.0,
    ) -> None:
        self._clock = clock
        self._ttl_seconds = ttl_seconds
        self._bindings: dict[str, tuple[WriteContract, float]] = {}
        self._lock = Lock()

    def bind(self, session_id: str, contract: WriteContract) -> None:
        """Bind a write contract to one session."""
        with self._lock:
            self._bindings[session_id] = (contract, self._clock())

    def resolve(self, session_id: str) -> WriteContract:
        """Return the contract bound to a session."""
        with self._lock:
            binding = self._bindings.get(session_id)
            if binding is None:
                raise UnboundSessionError(
                    f"no write contract bound to session {session_id!r}"
                )
            return binding[0]

    def release(self, session_id: str) -> None:
        """Drop a session binding if it exists."""
        with self._lock:
            self._bindings.pop(session_id, None)

    def purge_expired(self, now: float) -> None:
        """Drop bindings whose age is greater than the configured TTL."""
        with self._lock:
            expired = [
                session_id
                for session_id, (_, bound_at) in self._bindings.items()
                if now - bound_at > self._ttl_seconds
            ]
            for session_id in expired:
                del self._bindings[session_id]
