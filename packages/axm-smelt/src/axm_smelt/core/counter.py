"""Token counting with tiktoken."""

from __future__ import annotations

__all__ = ["count"]


def count(text: str, model: str = "o200k_base") -> int:
    """Return the token count for *text*.

    Uses tiktoken with *model* encoding.  Falls back to ``len(text) // 4``
    when tiktoken is unavailable.
    """
    try:
        import tiktoken

        enc = tiktoken.get_encoding(model)
        return len(enc.encode(text))
    except Exception:  # noqa: BLE001
        return len(text) // 4
