"""Golden byte-parity suite for ``render_result`` / ``record_table``.

Each representative payload shape (homogeneous record list, flat dict, short
scalar list, nested heterogeneous tree, empty list, empty dict, ``None``,
``bool``, scalar-only, mixed nesting) is rendered through
:func:`axm_ingot.render.render_result` and compared byte-for-byte against a
static golden ``.txt`` fixture captured from the canonical ``_render.py`` copy.

Fixtures live under ``tests/fixtures/snapshots/render/`` (terminal-newline
convention: each golden ends with a single trailing ``\n`` stripped before the
comparison). ``CASES`` is the single source of truth — the fixture generator
reads the very same payloads, so a drift in either walker breaks the parity.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ingot.render import record_table, render_result

pytestmark = pytest.mark.integration

SNAPSHOTS = Path(__file__).parent.parent / "fixtures" / "snapshots" / "render"

# name -> (tool, data, label)
CASES: dict[str, tuple[str, object, str]] = {
    "homogeneous_list": (
        "screen",
        [{"sym": "AAPL", "px": 190}, {"sym": "MSFT", "px": 410}],
        "2 hits",
    ),
    "flat_dict": ("confirm", {"ok": True, "count": 3, "name": "x"}, ""),
    "short_scalar_list": ("tags", ["a", "b", "c"], ""),
    "nested_tree": (
        "tree",
        [{"a": 1}, {"b": 2, "c": 3}, "leaf"],
        "",
    ),
    "empty_list": ("empty", [], ""),
    "empty_dict": ("empty", {}, ""),
    "none_value": ("probe", None, ""),
    "bool_value": ("flag", True, ""),
    "scalar_only": ("count", 3, ""),
    "mixed_nesting": (
        "detail",
        {
            "meta": {"n": 2, "ok": False},
            "rows": [{"k": 1, "v": 2}, {"k": 3, "v": 4}],
            "labels": ["x", "y"],
            "note": None,
            "nested": {"deep": {"leaf": 7}},
        },
        "sym",
    ),
}


def _golden(name: str) -> str:
    """Read a golden fixture, dropping the single terminal newline."""
    raw = (SNAPSHOTS / f"{name}.txt").read_text(encoding="utf-8")
    return raw[:-1] if raw.endswith("\n") else raw


@pytest.mark.parametrize("name", sorted(CASES))
def test_render_result_matches_golden_fixture(name: str) -> None:
    tool, data, label = CASES[name]
    assert render_result(tool, data, label=label) == _golden(name)


def test_record_table_is_lossless_header_and_rows() -> None:
    rows = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
    lines = record_table(rows, ["a", "b"])
    assert lines[0] == "a | b"
    assert lines[1:] == ["1 | 2", "3 | 4"]
