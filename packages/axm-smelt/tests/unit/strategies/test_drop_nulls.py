from __future__ import annotations

import json

import pytest

from axm_smelt.core.models import SmeltContext
from axm_smelt.strategies import get_strategy
from axm_smelt.strategies.base import SmeltStrategy


@pytest.fixture
def strategy() -> SmeltStrategy:
    return get_strategy("drop_nulls")


# --- Unit tests ---


def test_drop_nulls_basic(strategy: SmeltStrategy) -> None:
    data = json.dumps({"a": 1, "b": None, "c": ""})
    result = json.loads(strategy.apply(SmeltContext(text=data)).text)
    assert result == {"a": 1}


def test_drop_nulls_nested(strategy: SmeltStrategy) -> None:
    data = json.dumps({"a": {"b": None, "c": 1}, "d": []})
    result = json.loads(strategy.apply(SmeltContext(text=data)).text)
    assert result == {"a": {"c": 1}}


def test_drop_nulls_empty_after_clean(strategy: SmeltStrategy) -> None:
    data = json.dumps({"a": {"b": None}})
    result = json.loads(strategy.apply(SmeltContext(text=data)).text)
    assert result == {}


def test_drop_nulls_preserves_false_zero(strategy: SmeltStrategy) -> None:
    data = json.dumps({"a": False, "b": 0})
    result = json.loads(strategy.apply(SmeltContext(text=data)).text)
    assert result == {"a": False, "b": 0}


def test_drop_nulls_list_of_dicts(strategy: SmeltStrategy) -> None:
    data = json.dumps([{"a": 1, "b": None}])
    result = json.loads(strategy.apply(SmeltContext(text=data)).text)
    assert result == [{"a": 1}]


# --- Edge cases ---


def test_drop_nulls_all_null_values(strategy: SmeltStrategy) -> None:
    data = json.dumps({"a": None, "b": None})
    result = json.loads(strategy.apply(SmeltContext(text=data)).text)
    assert result == {}


def test_drop_nulls_empty_input(strategy: SmeltStrategy) -> None:
    result = strategy.apply(SmeltContext(text="")).text
    assert result == ""


def test_drop_nulls_non_json_input(strategy: SmeltStrategy) -> None:
    result = strategy.apply(SmeltContext(text="plain text")).text
    assert result == "plain text"
