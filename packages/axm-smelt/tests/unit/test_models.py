from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest

from axm_smelt.core.models import Format, SmeltContext


def test_context_is_frozen() -> None:
    ctx = SmeltContext(text='{"a":1}')
    with pytest.raises(FrozenInstanceError):
        ctx.text = "x"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        ctx.parsed = {}  # type: ignore[misc]


def test_text_constructor_caches_parsed() -> None:
    ctx = SmeltContext(text='{"a":1}')
    first = ctx.parsed
    second = ctx.parsed
    assert first is second
    assert first == {"a": 1}


def test_parsed_constructor_caches_text() -> None:
    ctx = SmeltContext(parsed={"a": 1}, format=Format.JSON)
    assert ctx.text == ctx.text
    assert json.loads(ctx.text) == {"a": 1}


def test_parsed_serialization_is_deterministic() -> None:
    a = SmeltContext(parsed={"b": 2, "a": 1}, format=Format.JSON)
    b = SmeltContext(parsed={"b": 2, "a": 1}, format=Format.JSON)
    assert a.text == b.text


def test_invalid_json_text_yields_none_parsed() -> None:
    ctx = SmeltContext(text="not json")
    assert ctx.parsed is None


def test_empty_text_yields_none_parsed() -> None:
    ctx = SmeltContext(text="")
    assert ctx.parsed is None
