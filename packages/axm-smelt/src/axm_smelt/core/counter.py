"""Token counting with tiktoken."""

from __future__ import annotations

import logging
from enum import StrEnum

import tiktoken

__all__ = ["CounterBackend", "count", "count_with_backend"]

_log = logging.getLogger(__name__)
_ENC: dict[str, tiktoken.Encoding] = {}

# Approximate proxy for tokenizers tiktoken does not ship a vocab for.
# Claude has no public tiktoken vocab; ``o200k_base`` is a *built-in* tiktoken
# encoding (no runtime network I/O) used here as an approximation (±10-20%, and
# the Claude tokenizer changed in 2026). For an *exact* Claude count, the
# consumer must read ``usage.input_tokens`` from the run (axm-harness), not smelt.
_CLAUDE_PROXY_ENCODING = "o200k_base"
_DEFAULT_PROXY_ENCODING = "o200k_base"

_TIKTOKEN_VALUE = "tiktoken"


class CounterBackend(StrEnum):
    """Backend used to produce a token count.

    Currently only :attr:`TIKTOKEN` exists; the enum is retained as the seam
    for a future HuggingFace/SentencePiece backend (Llama/Mistral/Gemma).
    """

    TIKTOKEN = _TIKTOKEN_VALUE


def _resolve_encoding(model: str) -> tiktoken.Encoding:
    """Resolve *model* to a tiktoken ``Encoding``.

    A ``claude*`` model (case-insensitive) routes to the approximate
    :data:`_CLAUDE_PROXY_ENCODING` proxy. OpenAI model names (e.g. ``gpt-4o``)
    resolve via ``encoding_for_model`` and raw encoding names (e.g.
    ``o200k_base``) via ``get_encoding``. Any genuinely unknown name falls
    through to the :data:`_DEFAULT_PROXY_ENCODING` proxy — never to a
    ``len // 4`` approximation.
    """
    if model.lower().startswith("claude"):
        return tiktoken.get_encoding(_CLAUDE_PROXY_ENCODING)
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        try:
            return tiktoken.get_encoding(model)
        except (KeyError, ValueError):
            return tiktoken.get_encoding(_DEFAULT_PROXY_ENCODING)


def count_with_backend(
    text: str, model: str = "o200k_base"
) -> tuple[int, CounterBackend]:
    """Return ``(token_count, backend)`` for *text*.

    Always counts with tiktoken (backend :attr:`CounterBackend.TIKTOKEN`):
    a ``claude*`` or otherwise unknown model is routed to the ``o200k_base``
    proxy encoding rather than a ``len // 4`` approximation.
    """
    enc = _ENC.get(model)
    if enc is None:
        enc = _resolve_encoding(model)
        _ENC[model] = enc
    return len(enc.encode(text)), CounterBackend.TIKTOKEN


def count(text: str, model: str = "o200k_base") -> int:
    """Return the token count for *text*.

    Uses tiktoken with *model* encoding; a ``claude*`` or unknown model is
    routed to the ``o200k_base`` proxy.
    """
    n, _ = count_with_backend(text, model)
    return n
