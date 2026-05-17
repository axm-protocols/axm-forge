from __future__ import annotations

import json

import pytest

from axm_smelt.core.models import SmeltContext
from axm_smelt.strategies import get_strategy
from axm_smelt.strategies.base import SmeltStrategy
from axm_smelt.strategies.round_numbers import RoundNumbersStrategy


@pytest.fixture
def strategy() -> SmeltStrategy:
    return get_strategy("round_numbers")


# --- Unit tests ---


def test_round_numbers_basic(strategy: SmeltStrategy) -> None:
    data = json.dumps({"a": 3.14159, "b": 2.71828})
    result = json.loads(strategy.apply(SmeltContext(text=data)).text)
    assert result == {"a": 3.14, "b": 2.72}


def test_round_numbers_integers(strategy: SmeltStrategy) -> None:
    data = json.dumps({"a": 42})
    result = json.loads(strategy.apply(SmeltContext(text=data)).text)
    assert result == {"a": 42}
    assert isinstance(result["a"], int)


def test_round_numbers_nested(strategy: SmeltStrategy) -> None:
    data = json.dumps({"a": {"b": 1.23456}})
    result = json.loads(strategy.apply(SmeltContext(text=data)).text)
    assert result == {"a": {"b": 1.23}}


def test_round_numbers_custom_precision() -> None:
    strategy = RoundNumbersStrategy(precision=0)
    data = json.dumps({"a": 3.7})
    result = json.loads(strategy.apply(SmeltContext(text=data)).text)
    assert result == {"a": 4.0}


def test_round_numbers_in_array(strategy: SmeltStrategy) -> None:
    data = json.dumps([1.111, 2.222, 3.333])
    result = json.loads(strategy.apply(SmeltContext(text=data)).text)
    assert result == [1.11, 2.22, 3.33]


# --- Edge cases ---


def test_round_numbers_float_in_string(strategy: SmeltStrategy) -> None:
    """String values that look like floats should not be rounded."""
    data = json.dumps({"a": "3.14"})
    result = json.loads(strategy.apply(SmeltContext(text=data)).text)
    assert result == {"a": "3.14"}


def test_round_numbers_negative_floats(strategy: SmeltStrategy) -> None:
    data = json.dumps({"a": -1.23456})
    result = json.loads(strategy.apply(SmeltContext(text=data)).text)
    assert result == {"a": -1.23}
