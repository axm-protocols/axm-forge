from __future__ import annotations

import json
import logging

import pytest

from axm_smelt.core.models import Format, SmeltContext
from axm_smelt.strategies.dedup_values import DedupValuesStrategy


@pytest.fixture
def strategy() -> DedupValuesStrategy:
    return DedupValuesStrategy()


def _ctx(payload: object) -> SmeltContext:
    return SmeltContext(text=json.dumps(payload), format=Format.JSON)


def test_dedup_passthrough_on_refs_collision(
    strategy: DedupValuesStrategy, caplog: pytest.LogCaptureFixture
) -> None:
    payload = {"_refs": {"x": "y"}, "data": ["abc" * 20] * 5}
    ctx = _ctx(payload)
    with caplog.at_level(logging.DEBUG, logger="axm_smelt.strategies.dedup_values"):
        result = strategy.apply(ctx)
    assert result.text == ctx.text
    assert any(
        "reserved top-level key" in rec.message and rec.levelno == logging.DEBUG
        for rec in caplog.records
    )


def test_dedup_passthrough_on_data_collision(
    strategy: DedupValuesStrategy,
) -> None:
    payload = {"_data": {"k": "v"}, "items": ["abc" * 20] * 5}
    ctx = _ctx(payload)
    result = strategy.apply(ctx)
    assert result.text == ctx.text


def test_dedup_proceeds_on_list_input_with_refs_string(
    strategy: DedupValuesStrategy,
) -> None:
    repeated = "abc" * 20
    payload = ["_refs", "_data", repeated, repeated, repeated]
    ctx = _ctx(payload)
    result = strategy.apply(ctx)
    parsed = json.loads(result.text)
    assert isinstance(parsed, dict)
    assert "_refs" in parsed and "_data" in parsed
    assert repeated in parsed["_refs"].values()


def test_dedup_normal_input_unchanged_behavior(
    strategy: DedupValuesStrategy,
) -> None:
    val = "long_repeated_value" * 5
    payload = {"a": val, "b": val, "c": val}
    ctx = _ctx(payload)
    result = strategy.apply(ctx)
    parsed = json.loads(result.text)
    assert set(parsed.keys()) == {"_refs", "_data"}
    assert val in parsed["_refs"].values()
    alias = next(a for a, s in parsed["_refs"].items() if s == val)
    assert parsed["_data"] == {"a": alias, "b": alias, "c": alias}
