"""Utils module."""

from __future__ import annotations

__all__ = ["normalize", "trim"]


def trim(s: str) -> str:
    """Strip whitespace."""
    return s.strip()


def normalize(s: str) -> str:
    """Lowercase + strip."""
    return s.strip().lower()
