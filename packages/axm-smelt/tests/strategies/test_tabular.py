from __future__ import annotations

import json

import pytest

from axm_smelt.core.models import SmeltContext
from axm_smelt.strategies.tabular import TabularStrategy


@pytest.fixture
def strategy() -> TabularStrategy:
    return TabularStrategy()


class TestTabularBasic:
    def test_tabular_basic(self, strategy: TabularStrategy) -> None:
        inp = '[{"name":"A","age":1},{"name":"B","age":2}]'
        result = strategy.apply(SmeltContext(text=inp)).text
        assert result == "name|age\nA|1\nB|2"

    def test_tabular_nested_values(self, strategy: TabularStrategy) -> None:
        data = json.dumps([{"a": 1, "b": {"nested": True}}])
        result = strategy.apply(SmeltContext(text=data)).text
        lines = result.split("\n")
        assert lines[0] == "a|b"
        # Nested dict value should be JSON-encoded
        assert '{"nested": true}' in lines[1]

    def test_tabular_empty_array(self, strategy: TabularStrategy) -> None:
        result = strategy.apply(SmeltContext(text="[]")).text
        assert result == "[]"

    def test_tabular_single_item(self, strategy: TabularStrategy) -> None:
        result = strategy.apply(SmeltContext(text='[{"a":1}]')).text
        assert result == "a\n1"

    def test_tabular_mixed_keys(self, strategy: TabularStrategy) -> None:
        data = json.dumps([{"a": 1, "b": 2}, {"a": 3, "c": 4}])
        result = strategy.apply(SmeltContext(text=data)).text
        lines = result.split("\n")
        headers = lines[0].split("|")
        assert "a" in headers
        assert "b" in headers
        assert "c" in headers
        # Row for {"a":3, "c":4} should have empty for missing key b
        row2_values = lines[2].split("|")
        b_idx = headers.index("b")
        assert row2_values[b_idx] == ""

    def test_tabular_non_array(self, strategy: TabularStrategy) -> None:
        text = '{"a":1}'
        result = strategy.apply(SmeltContext(text=text)).text
        assert result == text

    def test_tabular_non_dict_array(self, strategy: TabularStrategy) -> None:
        text = "[1,2,3]"
        result = strategy.apply(SmeltContext(text=text)).text
        assert result == text


class TestTabularEdgeCases:
    def test_pipe_in_value(self, strategy: TabularStrategy) -> None:
        data = json.dumps([{"a": "hello|world", "b": 1}])
        result = strategy.apply(SmeltContext(text=data)).text
        lines = result.split("\n")
        assert lines[0] == "a|b"
        # Value containing pipe must be JSON-encoded to avoid ambiguity
        assert '"hello|world"' in lines[1]

    def test_very_wide_table(self, strategy: TabularStrategy) -> None:
        obj = {f"key_{i:03d}": i for i in range(55)}
        data = json.dumps([obj])
        result = strategy.apply(SmeltContext(text=data)).text
        lines = result.split("\n")
        headers = lines[0].split("|")
        assert len(headers) == 55

    def test_boolean_null_values(self, strategy: TabularStrategy) -> None:
        data = json.dumps([{"a": True, "b": None}])
        result = strategy.apply(SmeltContext(text=data)).text
        lines = result.split("\n")
        assert lines[0] == "a|b"
        assert lines[1] == "true|null"
