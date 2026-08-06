"""Unit tests for near-miss diagnostics in ``axm_edit.core.engine``.

Every case drives the single zero-match construction site
``_not_found_error`` with in-memory lines (no real I/O).
"""

from __future__ import annotations

import pytest

from axm_edit.core.engine import _not_found_error
from axm_edit.models.operations import Edit, ValidationError

# Built from its code point: a raw U+00A0 in the source is unreadable (and
# rightly flagged as an ambiguous character by ruff RUF001).
NBSP = chr(0x00A0)


def _error(lines: list[str], old: str) -> ValidationError:
    """Build the zero-match validation error for *old* against *lines*."""
    return _not_found_error("sample.py", Edit(old=old, new="REPLACEMENT"), lines)


def test_tab_near_miss_is_located() -> None:
    """AC1: a tab-vs-space near miss names the line and the ``<TAB>`` marker."""
    lines = [
        "import os",
        "",
        "value\t= compute(x)",
        "return value",
    ]

    err = _error(lines, "value = compute(x)")

    assert err.error is not None
    assert "3" in err.error
    assert "<TAB>" in err.error
    assert "was not located" not in err.error


def test_trailing_spaces_are_marked() -> None:
    """AC1: each trailing space of the candidate renders as one ``<SP>``."""
    lines = [
        "alpha=1",
        "beta=2  ",
        "gamma=3",
    ]

    err = _error(lines, "beta=2")

    assert err.error is not None
    assert err.error.count("<SP>") == 2
    assert "2" in err.error


def test_nbsp_near_miss_is_marked() -> None:
    """AC1: a U+00A0 near miss renders as ``<NBSP>`` with its line number."""
    lines = [
        f"total{NBSP}= 42",
        "other = 7",
    ]

    err = _error(lines, "total = 42")

    assert err.error is not None
    assert "<NBSP>" in err.error
    assert "1" in err.error


@pytest.mark.parametrize(
    ("char", "marker"),
    [
        pytest.param(chr(0x2014), "<EM DASH>", id="em_dash"),
        pytest.param(
            chr(0x2019),
            "<RIGHT SINGLE QUOTATION MARK>",
            id="right_single_quote",
        ),
        pytest.param(
            chr(0x2500),
            "<BOX DRAWINGS LIGHT HORIZONTAL>",
            id="box_drawings_light_horizontal",
        ),
    ],
)
def test_unicode_punctuation_is_named_never_raw(char: str, marker: str) -> None:
    """AC2: the differing character is named, and never echoed raw."""
    lines = [
        "import os",
        "",
        "def build() -> str:",
        f"banner = {'x' * 8}{char}{'y' * 8}",
    ]

    err = _error(lines, f"banner = {'x' * 8}-{'y' * 8}")

    assert err.error is not None
    assert "4" in err.error
    assert marker in err.error
    assert char not in err.error


def test_line_boundary_is_reported_as_such() -> None:
    """AC3: an anchor spanning two file lines names line 5 and ``<LF>``."""
    lines = [
        "import os",
        "",
        "def main() -> int:",
        "prefix = 1",
        "result = compute_total(alpha, beta, gamma)",
        " + prefix",
        "return result",
        "# end",
    ]

    err = _error(lines, lines[4] + lines[5])

    assert err.error is not None
    assert "5" in err.error
    assert "<LF>" in err.error


def test_no_candidate_leaves_line_none() -> None:
    """AC4: with no similar line, ``line`` stays ``None`` and the text says so."""
    lines = ["alpha", "beta", "gamma", "delta"]

    err = _error(lines, "ZZZ_MISSING_ANCHOR_TOKEN_123")

    assert err.line is None
    assert err.actual is None
    assert err.error is not None
    assert "no similar line" in err.error.lower()


def test_structured_fields_mirror_the_candidate() -> None:
    """AC5: ``line``/``actual`` mirror the candidate line and its raw text."""
    lines = [
        "def f():",
        "    a = 1",
        f"total{NBSP}= 42",
        "    return total",
    ]

    err = _error(lines, "total = 42")

    assert err.line == 3
    assert err.actual == lines[2]


def test_long_candidate_stays_bounded() -> None:
    """AC6: a 10 000-char candidate is summarised, never dumped in full."""
    lines = ["header = 1", "x" * 10_000]

    err = _error(lines, "x" * 9_990 + "z" * 10)

    assert err.error is not None
    assert "2" in err.error
    assert len(err.error) <= 400


def test_ambiguous_match_line_list_is_truncated() -> None:
    """AC2: 12 identical anchors list 5 lines plus a ``(+7 more)`` suffix."""
    anchor = "value = compute(x)"
    lines = ["import os"]
    for _ in range(12):
        lines.append(anchor)
        lines.append("filler = 0")

    err = _error(lines, anchor)

    assert err.error is not None
    assert "Ambiguous match:" in err.error
    for first_hit in ("2", "4", "6", "8", "10"):
        assert first_hit in err.error
    assert "(+7 more)" in err.error
    assert "24" not in err.error
