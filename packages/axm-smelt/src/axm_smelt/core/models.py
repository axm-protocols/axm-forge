"""Core models for axm-smelt."""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from functools import cached_property
from typing import cast

from pydantic import BaseModel

from axm_smelt._types import JsonValue
from axm_smelt.core.counter import CounterBackend

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


_SENTINEL: object = object()


@dataclass(frozen=True)
class SmeltContext:
    """Immutable runtime context passed through the strategy pipeline.

    One of ``text`` or ``parsed`` is the source of truth; the other is
    derived deterministically and cached on first access. The two
    representations cannot drift because the instance is frozen.
    """

    format: Format = Format.TEXT
    _src_text: str | None = field(default=None, repr=False)
    _src_parsed: JsonValue | object = field(default=_SENTINEL, repr=False)

    def __init__(
        self,
        text: str | None = None,
        format: Format = Format.TEXT,
        parsed: JsonValue | object = _SENTINEL,
    ) -> None:
        object.__setattr__(self, "format", format)
        object.__setattr__(self, "_src_text", text)
        object.__setattr__(self, "_src_parsed", parsed)

    @cached_property
    def text(self) -> str:
        """Text representation, derived from ``parsed`` when not provided."""
        if self._src_text is not None:
            return self._src_text
        if self._src_parsed is _SENTINEL or self._src_parsed is None:
            return ""
        return json.dumps(
            self._src_parsed,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    @cached_property
    def parsed(self) -> dict[str, JsonValue] | list[JsonValue] | None:
        """Parsed JSON, derived from ``text`` when not provided."""
        if self._src_parsed is not _SENTINEL:
            return cast(
                "dict[str, JsonValue] | list[JsonValue] | None", self._src_parsed
            )
        if not self._src_text:
            return None
        try:
            return cast(
                "dict[str, JsonValue] | list[JsonValue] | None",
                json.loads(self._src_text),
            )
        except (json.JSONDecodeError, ValueError, TypeError):
            return None


class SmeltReport(BaseModel):  # type: ignore[explicit-any]  # reason: pydantic plugin synthesizes __init__ with Any kwargs
    """Report produced by the smelt pipeline."""

    original: str
    compacted: str
    original_tokens: int
    compacted_tokens: int
    savings_pct: float
    format: Format
    strategies_applied: list[str]
    strategy_estimates: dict[str, float] = {}
    counter_backend: CounterBackend = CounterBackend.TIKTOKEN
