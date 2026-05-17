from __future__ import annotations

import json
import logging

import pytest

from axm_smelt.core.models import Format, SmeltContext
from axm_smelt.strategies import REGISTRY
from axm_smelt.strategies.dedup_values import (
    DedupValuesStrategy,
    collect_strings,
    replace_strings,
)

_LONG = "a]" * 20  # 40 chars, above _MIN_LENGTH=20


@pytest.fixture
def strategy() -> DedupValuesStrategy:
    return DedupValuesStrategy()


def _ctx(payload: object) -> SmeltContext:
    return SmeltContext(text=json.dumps(payload), format=Format.JSON)


# --- collect_strings ---


def test_collect_strings_nested() -> None:
    """Deeply nested JSON with repeated strings returns correct frequency map."""
    data = {"a": {"b": {"c": _LONG}}, "d": [_LONG, {"e": _LONG}]}
    strings: list[str] = []
    collect_strings(data, strings)
    assert strings.count(_LONG) == 3


def test_collect_strings_empty_object() -> None:
    strings: list[str] = []
    collect_strings({}, strings)
    assert strings == []


def test_collect_strings_no_duplicates() -> None:
    """All unique string values — no dedup candidates."""
    data = {"a": "x" * 25, "b": "y" * 25, "c": "z" * 25}
    strings: list[str] = []
    collect_strings(data, strings)
    # All collected but each appears once
    assert len(strings) == 3
    assert len(set(strings)) == 3


def test_collect_strings_short_strings_ignored() -> None:
    """Strings shorter than _MIN_LENGTH are not collected."""
    data = {"a": "short", "b": ["tiny", "small"]}
    strings: list[str] = []
    collect_strings(data, strings)
    assert strings == []


def test_collect_strings_list_of_strings() -> None:
    data = [_LONG, _LONG]
    strings: list[str] = []
    collect_strings(data, strings)
    assert len(strings) == 2


# --- replace_strings ---


def test_replace_strings_mixed_types() -> None:
    """Only strings in lookup are replaced; numbers, booleans, nulls untouched."""
    lookup = {_LONG: "$R0"}
    data = {"s": _LONG, "n": 42, "b": True, "null": None, "list": [_LONG, 3.14]}
    result = replace_strings(data, lookup)
    assert result["s"] == "$R0"
    assert result["n"] == 42
    assert result["b"] is True
    assert result["null"] is None
    assert result["list"] == ["$R0", 3.14]


def test_replace_strings_no_match() -> None:
    """Strings not in lookup are returned as-is."""
    data = {"a": "not in lookup"}
    result = replace_strings(data, {})
    assert result == {"a": "not in lookup"}


def test_replace_strings_nested_dict() -> None:
    lookup = {_LONG: "$R0"}
    data = {"outer": {"inner": _LONG}}
    result = replace_strings(data, lookup)
    assert result == {"outer": {"inner": "$R0"}}


# --- DedupValuesStrategy.apply ---


def test_dedup_threshold_boundary(strategy: DedupValuesStrategy) -> None:
    """String appearing exactly at _MIN_OCCURRENCES=2 is deduped."""
    data = {"a": _LONG, "b": _LONG}
    ctx = SmeltContext(text=json.dumps(data))
    result = strategy.apply(ctx)
    parsed = json.loads(result.text)
    assert "_refs" in parsed
    assert "_data" in parsed
    # The alias should map back to _LONG
    alias = next(iter(parsed["_refs"]))
    assert parsed["_refs"][alias] == _LONG


@pytest.mark.parametrize(
    "data",
    [
        pytest.param({"a": _LONG}, id="below_occurrence_threshold"),
        pytest.param({"a": "", "b": ""}, id="below_length_threshold"),
    ],
)
def test_dedup_no_qualifying_duplicates_passthrough(
    strategy: DedupValuesStrategy, data: dict[str, str]
) -> None:
    """No qualifying duplicates (occurrence or length below threshold)."""
    ctx = SmeltContext(text=json.dumps(data))
    result = strategy.apply(ctx)
    assert result is ctx


def test_dedup_preserves_keys(strategy: DedupValuesStrategy) -> None:
    """Keys matching values are NOT deduplicated — only values are."""
    # Use _LONG as both a key and repeated value
    data = {_LONG: _LONG, "other": _LONG}
    ctx = SmeltContext(text=json.dumps(data))
    result = strategy.apply(ctx)
    parsed = json.loads(result.text)
    # The original key must still be present verbatim
    assert _LONG in parsed["_data"]


def test_dedup_unicode_strings(strategy: DedupValuesStrategy) -> None:
    """Unicode string values are handled correctly."""
    ustr = "éèê" * 10  # 30 chars of accented chars
    data = {"a": ustr, "b": ustr, "c": ustr}
    ctx = SmeltContext(text=json.dumps(data))
    result = strategy.apply(ctx)
    parsed = json.loads(result.text)
    alias = next(iter(parsed["_refs"]))
    assert parsed["_refs"][alias] == ustr


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("just plain text", id="non_json"),
        pytest.param("{invalid json", id="invalid_json"),
        pytest.param("", id="empty"),
    ],
)
def test_dedup_unparseable_passthrough(
    strategy: DedupValuesStrategy, text: str
) -> None:
    """Non-JSON / invalid / empty text is returned unchanged."""
    ctx = SmeltContext(text=text)
    result = strategy.apply(ctx)
    assert result is ctx


def test_dedup_with_parsed_context(strategy: DedupValuesStrategy) -> None:
    """When ctx.parsed is pre-populated, json.loads is skipped."""
    data = {"a": _LONG, "b": _LONG}
    ctx = SmeltContext(text="", parsed=data)
    result = strategy.apply(ctx)
    parsed = json.loads(result.text)
    assert "_refs" in parsed


def test_dedup_all_values_identical(strategy: DedupValuesStrategy) -> None:
    """Every value is the same string — maximum dedup applied."""
    data = {f"k{i}": _LONG for i in range(10)}
    ctx = SmeltContext(text=json.dumps(data))
    result = strategy.apply(ctx)
    parsed = json.loads(result.text)
    assert len(parsed["_refs"]) == 1
    # All values in _data should be the alias
    alias = next(iter(parsed["_refs"]))
    for v in parsed["_data"].values():
        assert v == alias


def test_dedup_very_long_strings(strategy: DedupValuesStrategy) -> None:
    """Values > 1000 chars repeated are handled without issues."""
    long_val = "x" * 1500
    data = {"a": long_val, "b": long_val}
    ctx = SmeltContext(text=json.dumps(data))
    result = strategy.apply(ctx)
    parsed = json.loads(result.text)
    assert parsed["_refs"]["$R0"] == long_val


def test_dedup_json_array_input(strategy: DedupValuesStrategy) -> None:
    """Top-level JSON array input is handled."""
    data = [_LONG, _LONG, "short"]
    ctx = SmeltContext(text=json.dumps(data))
    result = strategy.apply(ctx)
    parsed = json.loads(result.text)
    assert "_refs" in parsed
    assert "_data" in parsed


def test_dedup_sorting_by_savings(strategy: DedupValuesStrategy) -> None:
    """Aliases are assigned by savings (length * count) descending."""
    short_dup = "s" * 21  # 21 chars, appears 5 times -> savings 105
    long_dup = "L" * 50  # 50 chars, appears 3 times -> savings 150
    data = [
        short_dup,
        short_dup,
        short_dup,
        short_dup,
        short_dup,
        long_dup,
        long_dup,
        long_dup,
    ]
    ctx = SmeltContext(text=json.dumps(data))
    result = strategy.apply(ctx)
    parsed = json.loads(result.text)
    # $R0 should be the higher-savings string (long_dup)
    assert parsed["_refs"]["$R0"] == long_dup
    assert parsed["_refs"]["$R1"] == short_dup


# --- reserved top-level key collisions ---


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


# --- registry name ---


def test_dedup_strategy_new_name() -> None:
    assert DedupValuesStrategy().name == "dedup_values_with_refs"


def test_registry_resolves_new_name() -> None:
    assert REGISTRY["dedup_values_with_refs"] is DedupValuesStrategy


def test_registry_rejects_old_name() -> None:
    with pytest.raises(KeyError):
        REGISTRY["dedup_values"]
