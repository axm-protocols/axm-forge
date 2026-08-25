"""Unit tests for the ``axm_ingot.render`` compact-text primitives."""

from __future__ import annotations

from axm_ingot import render as render_mod
from axm_ingot.render import (
    compact_table,
    format_count,
    format_size,
    header,
    labeled_block,
    record_table,
    render_result,
    truncate,
)


def test_header_renders_tool_pipe_summary() -> None:
    assert header("audit", "3 findings") == "audit | 3 findings"


def test_labeled_block_renders_label_and_indented_lines() -> None:
    out = labeled_block("Errors", ["a", "b"])
    lines = out.splitlines()
    assert lines[0] == "Errors"
    assert lines[1].strip() == "a"
    assert lines[2].strip() == "b"
    assert lines[1].startswith("  ")


def test_labeled_block_empty_lines_yields_no_dangling_block() -> None:
    assert labeled_block("Errors", []) == ""


def test_compact_table_aligns_columns_for_regular_rows() -> None:
    out = compact_table([["a", "1"], ["bbb", "22"]], headers=["k", "v"])
    lines = out.splitlines()
    assert lines[0].startswith("k")
    # first column padded to width of widest cell ("bbb")
    col_starts = [line.index("1" if "1" in line else "2") for line in lines[1:]]
    assert len(set(col_starts)) == 1


def test_compact_table_tolerates_ragged_and_wide_rows() -> None:
    out = compact_table([["a"], ["b", "x" * 200, "c"]])
    assert "x" * 200 in out
    assert "a" in out and "c" in out


def test_truncate_bounds_text_and_appends_ellipsis() -> None:
    out = truncate("x" * 100, 10)
    assert len(out) <= 10 + 1
    assert out.endswith("…")


def test_truncate_leaves_short_text_unchanged() -> None:
    assert truncate("ok", 10) == "ok"


def test_compact_table_none_values_render_as_empty() -> None:
    out = compact_table([[None, "1"]])
    assert "None" not in out
    assert "1" in out


def test_unicode_content_preserved_through_primitives() -> None:
    out = header("tool", "café ✓ 日本")
    assert "café ✓ 日本" in out


def test_format_count_and_format_size_render_human_readable() -> None:
    assert format_count(1500) == "1.5K"
    assert format_count(42) == "42"
    assert format_size(2048) == "2.0 KB"
    assert format_size(512) == "512 B"


def test_primitive_composition_matches_single_block_golden_sample() -> None:
    # Captured single-block sample: a header line plus one labeled block. The
    # golden is inlined (unit level = no file I/O) and is a real behavioral
    # assertion — a no-op ``labeled_block`` would drop the indented body.
    top = header("scan", "2 hits")
    block = labeled_block("Hits", ["a.py", "b.py"])
    text = "\n".join([top, block])

    assert text == "scan | 2 hits\nHits\n  a.py\n  b.py"


def test_render_result_and_record_table_are_exported() -> None:
    assert "render_result" in render_mod.__all__
    assert "record_table" in render_mod.__all__
    assert callable(render_result)
    assert callable(record_table)


def test_render_result_renders_scalar_only_payload_in_arrow_form() -> None:
    out = render_result("t", {"count": 3})
    assert " → " not in out  # a dict payload is not the top-level arrow form
    assert out == "t\ncount=3"  # single-key flat dict renders inline

    assert render_result("t", 3) == "t → 3"
    assert render_result("t", None) == "t → —"
    assert render_result("t", True) == "t → yes"
    assert render_result("t", False) == "t → no"


def test_render_result_never_raises_on_arbitrary_object() -> None:
    out = render_result("t", object())
    assert isinstance(out, str)

    cyclic: dict[str, object] = {}
    cyclic["self"] = cyclic
    result = render_result("t", cyclic)
    assert isinstance(result, str)


def test_record_table_emits_lossless_header_and_value_rows() -> None:
    rows = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
    lines = record_table(rows, ["a", "b"])
    assert lines[0] == "a | b"
    assert lines[1:] == ["1 | 2", "3 | 4"]

    indented = record_table(rows, ["a", "b"], indent=1)
    assert indented[0] == "  a | b"
    assert all(line.startswith("  ") for line in indented)
