from __future__ import annotations

import json

import pytest

from axm_smelt.core.models import SmeltContext
from axm_smelt.strategies.tabular import (
    TabularStrategy,
    collect_ordered_keys,
    render_rows,
    to_table,
)


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


# --- merged from test_tabular_helpers.py ---


def test_collect_ordered_keys_preserves_order() -> None:
    items = [{"b": 1, "a": 2}, {"a": 3, "c": 4}]
    result = collect_ordered_keys(items)
    assert result == ["b", "a", "c"]


def test_collect_ordered_keys_empty() -> None:
    result = collect_ordered_keys([])
    assert result == []


def test_render_rows_with_missing_keys() -> None:
    items = [{"a": 1, "b": 2}, {"a": 3}]
    keys = ["a", "b"]
    rows = render_rows(items, keys)
    assert len(rows) == 2
    # Second row should have empty string for missing key "b"
    assert rows[1].split("|")[1] == ""


def test_single_item_list() -> None:
    result = to_table([{"a": 1}])
    assert result is not None
    lines = result.split("\n")
    assert len(lines) == 2  # header + 1 row
    assert lines[0] == "a"


def test_all_keys_identical() -> None:
    result = to_table([{"a": 1}, {"a": 2}])
    assert result is not None
    lines = result.split("\n")
    assert lines[0] == "a"  # single-column header
    assert len(lines) == 3  # header + 2 rows


def test_nested_values_in_cells() -> None:
    result = to_table([{"a": {"b": 1}}])
    assert result is not None
    lines = result.split("\n")
    # Nested dict should be JSON-serialized via _format_cell
    cell = lines[1]
    assert "b" in cell
    assert "1" in cell
