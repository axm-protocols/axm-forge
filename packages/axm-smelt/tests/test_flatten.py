from __future__ import annotations

import json
from typing import Any

import pytest

from axm_smelt.core.models import SmeltContext
from axm_smelt.strategies import get_strategy
from axm_smelt.strategies.base import SmeltStrategy
from axm_smelt.strategies.flatten import FlattenStrategy


@pytest.fixture
def strategy() -> SmeltStrategy:
    return get_strategy("flatten")


# --- Unit tests ---


def test_flatten_basic(strategy: SmeltStrategy) -> None:
    data = json.dumps({"a": {"b": 1}})
    result = json.loads(strategy.apply(SmeltContext(text=data)).text)
    assert result == {"a.b": 1}


def test_flatten_deep(strategy: SmeltStrategy) -> None:
    data = json.dumps({"a": {"b": {"c": 1}}})
    result = json.loads(strategy.apply(SmeltContext(text=data)).text)
    assert result == {"a.b.c": 1}


def test_flatten_multi_key_no_flatten(strategy: SmeltStrategy) -> None:
    data = json.dumps({"a": {"b": 1, "c": 2}})
    result = json.loads(strategy.apply(SmeltContext(text=data)).text)
    assert result == {"a": {"b": 1, "c": 2}}


def test_flatten_with_depth_limit() -> None:
    strategy = FlattenStrategy(max_depth=1)
    data = json.dumps({"a": {"b": {"c": 1}}})
    result = json.loads(strategy.apply(SmeltContext(text=data)).text)
    assert result == {"a.b": {"c": 1}}


def test_flatten_preserves_arrays(strategy: SmeltStrategy) -> None:
    data = json.dumps({"a": [1, 2]})
    result = json.loads(strategy.apply(SmeltContext(text=data)).text)
    assert result == {"a": [1, 2]}


# --- Edge cases ---


def test_flatten_circular_like_nesting(strategy: SmeltStrategy) -> None:
    """20 levels deep single-child wrappers should all collapse."""
    data: Any = "value"
    for i in range(19, -1, -1):
        data = {f"level{i}": data}
    text = json.dumps(data)
    result = json.loads(strategy.apply(SmeltContext(text=text)).text)
    expected_key = ".".join(f"level{i}" for i in range(20))
    assert result == {expected_key: "value"}
