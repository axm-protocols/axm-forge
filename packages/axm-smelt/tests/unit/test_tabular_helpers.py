from __future__ import annotations

from axm_smelt.strategies.tabular import _collect_ordered_keys, _render_rows

# --- Unit tests ---


def test_collect_ordered_keys_preserves_order() -> None:
    items = [{"b": 1, "a": 2}, {"a": 3, "c": 4}]
    result = _collect_ordered_keys(items)
    assert result == ["b", "a", "c"]


def test_collect_ordered_keys_empty() -> None:
    result = _collect_ordered_keys([])
    assert result == []


def test_render_rows_with_missing_keys() -> None:
    items = [{"a": 1, "b": 2}, {"a": 3}]
    keys = ["a", "b"]
    rows = _render_rows(items, keys)
    assert len(rows) == 2
    # Second row should have empty string for missing key "b"
    assert rows[1].split("|")[1] == ""


# --- Edge cases ---


def test_single_item_list() -> None:
    from axm_smelt.strategies.tabular import _to_table

    result = _to_table([{"a": 1}])
    assert result is not None
    lines = result.split("\n")
    assert len(lines) == 2  # header + 1 row
    assert lines[0] == "a"


def test_all_keys_identical() -> None:
    from axm_smelt.strategies.tabular import _to_table

    result = _to_table([{"a": 1}, {"a": 2}])
    assert result is not None
    lines = result.split("\n")
    assert lines[0] == "a"  # single-column header
    assert len(lines) == 3  # header + 2 rows


def test_nested_values_in_cells() -> None:
    from axm_smelt.strategies.tabular import _to_table

    result = _to_table([{"a": {"b": 1}}])
    assert result is not None
    lines = result.split("\n")
    # Nested dict should be JSON-serialized via _format_cell
    cell = lines[1]
    assert "b" in cell
    assert "1" in cell
