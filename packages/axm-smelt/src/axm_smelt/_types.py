"""Shared type aliases for axm-smelt (package-level, no internal deps)."""

from __future__ import annotations

__all__ = ["JsonValue"]

type JsonValue = (
    str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
)
