"""Token counting with tiktoken."""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any

import tiktoken

__all__ = ["CounterBackend", "count", "count_with_backend"]

_log = logging.getLogger(__name__)
_ENC: dict[str, Any] = {}
_warned: bool = False


class CounterBackend(StrEnum):
    """Backend used to produce a token count."""

    TIKTOKEN = "tiktoken"
    FALLBACK = "fallback"


def count_with_backend(
    text: str, model: str = "o200k_base"
) -> tuple[int, CounterBackend]:
    """Return ``(token_count, backend)`` for *text*.

    Falls back to ``len(text) // 4`` when tiktoken is unavailable, and emits
    a single warning the first time the fallback path is taken in a process.
    """
    global _warned
    try:
        enc = _ENC.get(model)
        if enc is None:
            enc = tiktoken.get_encoding(model)
            _ENC[model] = enc
        return len(enc.encode(text)), CounterBackend.TIKTOKEN
    except Exception:  # noqa: BLE001
        if not _warned:
            _log.warning("tiktoken unavailable, using approximate len//4 fallback")
            _warned = True
        return len(text) // 4, CounterBackend.FALLBACK


def count(text: str, model: str = "o200k_base") -> int:
    """Return the token count for *text*.

    Uses tiktoken with *model* encoding.  Falls back to ``len(text) // 4``
    when tiktoken is unavailable.
    """
    n, _ = count_with_backend(text, model)
    return n
