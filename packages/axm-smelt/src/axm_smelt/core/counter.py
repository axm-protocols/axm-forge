"""Token counting with tiktoken."""

from __future__ import annotations

from typing import Any

import tiktoken

__all__ = ["count"]

_ENC: dict[str, Any] = {}


def count(text: str, model: str = "o200k_base") -> int:
    """Return the token count for *text*.

    Uses tiktoken with *model* encoding.  Falls back to ``len(text) // 4``
    when tiktoken is unavailable.
    """
    try:
        enc = _ENC.get(model)
        if enc is None:
            enc = tiktoken.get_encoding(model)
            _ENC[model] = enc
        return len(enc.encode(text))
    except Exception:  # noqa: BLE001
        return len(text) // 4
