"""Token counting with tiktoken."""

from __future__ import annotations

import logging
from enum import StrEnum

import tiktoken

__all__ = ["CounterBackend", "count", "count_with_backend"]

_log = logging.getLogger(__name__)
_ENC: dict[str, tiktoken.Encoding] = {}
_warned: bool = False


def _resolve_encoding(model: str) -> tiktoken.Encoding:
    """Resolve *model* to a tiktoken ``Encoding``.

    Accepts both OpenAI model names (e.g. ``gpt-4o``) via
    ``encoding_for_model`` and raw encoding names (e.g. ``o200k_base``) via
    ``get_encoding``. Raises ``KeyError``/``ValueError`` for a genuinely
    unknown name, or ``ImportError`` if tiktoken is unavailable.
    """
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding(model)


def reset_warned() -> None:
    """Reset the one-shot warning flag (test seam)."""
    global _warned
    _warned = False


_TIKTOKEN_VALUE = "tiktoken"
_FALLBACK_VALUE = "fallback"


class CounterBackend(StrEnum):
    """Backend used to produce a token count."""

    TIKTOKEN = _TIKTOKEN_VALUE
    FALLBACK = _FALLBACK_VALUE


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
            enc = _resolve_encoding(model)
            _ENC[model] = enc
        return len(enc.encode(text)), CounterBackend.TIKTOKEN
    except ImportError:
        if not _warned:
            _log.warning("tiktoken unavailable, using approximate len//4 fallback")
            _warned = True
        return len(text) // 4, CounterBackend.FALLBACK
    except (KeyError, ValueError):
        if not _warned:
            _log.warning(
                "unknown model/encoding %r, using approximate len//4 fallback", model
            )
            _warned = True
        return len(text) // 4, CounterBackend.FALLBACK


def count(text: str, model: str = "o200k_base") -> int:
    """Return the token count for *text*.

    Uses tiktoken with *model* encoding.  Falls back to ``len(text) // 4``
    when tiktoken is unavailable.
    """
    n, _ = count_with_backend(text, model)
    return n
