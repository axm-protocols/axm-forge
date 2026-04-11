"""Core models for axm-smelt."""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

__all__ = ["Format", "SmeltContext", "SmeltReport"]


class Format(enum.Enum):
    """Supported input formats."""

    JSON = "json"
    YAML = "yaml"
    XML = "xml"
    TOML = "toml"
    CSV = "csv"
    MARKDOWN = "markdown"
    TEXT = "text"


_SENTINEL = object()


@dataclass
class SmeltContext:
    """Internal runtime context passed through the strategy pipeline."""

    _text: str = field(repr=False)
    format: Format = Format.TEXT
    _parsed: object = field(default=_SENTINEL, repr=False)

    def __init__(
        self,
        text: str = "",
        format: Format = Format.TEXT,
        parsed: object = _SENTINEL,
    ) -> None:
        self._text = text
        self.format = format
        self._parsed = parsed

    @property
    def text(self) -> str:
        """Current text representation, re-serialized from parsed if needed."""
        if self._text is None:
            # Re-serialize from parsed
            self._text = json.dumps(self._parsed)
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        self._text = value
        self._parsed = _SENTINEL  # invalidate parsed cache

    @property
    def parsed(self) -> dict[str, Any] | list[Any] | None:
        """Lazy-parsed structured data, decoded from text on first access."""
        if self._parsed is _SENTINEL:
            try:
                self._parsed = json.loads(self._text)
            except (json.JSONDecodeError, ValueError, TypeError):
                self._parsed = None
        return self._parsed  # type: ignore[return-value]

    @parsed.setter
    def parsed(self, value: dict[str, Any] | list[Any] | None) -> None:
        self._parsed = value
        self._text = None  # type: ignore[assignment]  # invalidate text cache


class SmeltReport(BaseModel):
    """Report produced by the smelt pipeline."""

    original: str
    compacted: str
    original_tokens: int
    compacted_tokens: int
    savings_pct: float
    format: Format
    strategies_applied: list[str]
    strategy_estimates: dict[str, float] = {}
