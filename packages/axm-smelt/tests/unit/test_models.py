from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest

from axm_smelt.core.models import Format, SmeltContext, SmeltReport
from axm_smelt.strategies.base import SmeltStrategy


def test_context_is_frozen() -> None:
    ctx = SmeltContext(text='{"a":1}')
    with pytest.raises(FrozenInstanceError):
        ctx.text = "x"
    with pytest.raises(FrozenInstanceError):
        ctx.parsed = {}


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


def test_smelt_report_fields() -> None:
    report = SmeltReport(
        original="hello world",
        compacted="hello world",
        original_tokens=10,
        compacted_tokens=8,
        savings_pct=20.0,
        format=Format.TEXT,
        strategies_applied=["minify"],
    )
    assert report.original == "hello world"
    assert report.compacted == "hello world"
    assert report.original_tokens == 10
    assert report.compacted_tokens == 8
    assert report.savings_pct == 20.0
    assert report.format == Format.TEXT
    assert report.strategies_applied == ["minify"]


def test_strategy_abc() -> None:
    with pytest.raises(TypeError):

        class Incomplete(SmeltStrategy):
            pass

        Incomplete()  # type: ignore[abstract]
