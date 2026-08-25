"""Unit tests for the anchor-miss diagnostic kernel.

Covers AC1 (invisible rendering), AC2 (difference explanation),
AC3/AC4 (closest candidate and its absence) and AC5 (hard bounds).
Everything is in-memory: no filesystem, no subprocess, no network.
"""

from __future__ import annotations

import importlib
import re
from typing import Any

from axm_edit.core.diagnostics import (
    MAX_CANDIDATE_LINES,
    MAX_DIAGNOSTIC_CHARS,
    MAX_SNIPPET_CHARS,
    Candidate,
    closest_candidate,
    explain_difference,
    render_invisibles,
)

NBSP = chr(0xA0)
EM_DASH = chr(0x2014)
RIGHT_QUOTE = chr(0x2019)
BOX_HORIZONTAL = chr(0x2500)
ANCHOR = "    result = compute_total(values)"
TAB_VARIANT = "\tresult = compute_total(values)"
NBSP_VARIANT = f"    result ={NBSP}compute_total(values)"


def _diagnostics_attr(name: str) -> Any:
    """Return the public ``core.diagnostics`` symbol ``name``.

    Resolved at call time so a missing near-miss API is an ordinary
    assertion failure inside the test, never a collection error.
    """
    module = importlib.import_module("axm_edit.core.diagnostics")
    attribute = getattr(module, name, None)

    assert attribute is not None, f"axm_edit.core.diagnostics.{name} is missing"
    return attribute


def _near_miss(lines: list[str], old: str) -> Any:
    """Call the public ``explain_near_miss`` assembler on ``lines``/``old``."""
    return _diagnostics_attr("explain_near_miss")(lines, old)


def test_render_invisibles_names_tab_trailing_space_nbsp_and_crlf() -> None:
    """AC1: tab, trailing spaces, NBSP and CR/LF become named markers."""
    rendered = render_invisibles(f"def f():\thello{NBSP}world  \r\n")

    assert "<TAB>" in rendered
    assert "<SP>" in rendered
    assert "<NBSP>" in rendered
    assert "<CR>" in rendered
    assert "<LF>" in rendered
    assert "def f():" in rendered
    assert "hello" in rendered
    assert "world" in rendered
    assert "\t" not in rendered
    assert "\r" not in rendered
    assert "\n" not in rendered
    assert NBSP not in rendered


def test_render_invisibles_names_box_drawing_character() -> None:
    """AC1: a non-ASCII punctuation char is named, never dumped raw."""
    rendered = render_invisibles("left │ right")

    assert "BOX DRAWINGS" in rendered or "<U+2502>" in rendered
    assert "│" not in rendered
    assert "left" in rendered
    assert "right" in rendered


def test_explain_difference_names_em_dash_and_first_column() -> None:
    """AC2: hyphen vs em dash is explained on one line with the char name."""
    explanation = explain_difference("a - b", "a — b")

    assert "\n" not in explanation
    assert "EM DASH" in explanation or "<U+2014>" in explanation
    assert re.search(r"\b[23]\b", explanation) is not None
    assert "—" not in explanation


def test_closest_candidate_finds_whitespace_only_near_miss() -> None:
    """AC3: the tab-indented twin is reported at its 1-based line, twice."""
    lines = [
        "def compute():",
        "    values = [1, 2, 3]",
        TAB_VARIANT,
        "    return result",
    ]

    first = closest_candidate(lines, ANCHOR)
    second = closest_candidate(lines, ANCHOR)

    assert isinstance(first, Candidate)
    assert first.line == 3
    assert first.ratio > 0.9
    assert first.text == TAB_VARIANT
    assert first == second


def test_closest_candidate_ties_resolve_to_lowest_line() -> None:
    """AC3: two identical near misses resolve to the lowest line number."""
    lines = [
        "def compute():",
        TAB_VARIANT,
        "    a = 1",
        "    b = 2",
        "    c = 3",
        "    d = 4",
        TAB_VARIANT,
        "    return result",
    ]

    candidate = closest_candidate(lines, ANCHOR)

    assert candidate is not None
    assert candidate.line == 2


def test_closest_candidate_returns_none_for_unrelated_anchor() -> None:
    """AC4: below the similarity threshold, no best-effort guess is made."""
    lines = [
        "The quick brown fox",
        "jumps over the lazy dog",
        "and then rests in the shade.",
    ]

    assert closest_candidate(lines, "zzz_totally_absent()") is None


def test_rendering_and_explanation_respect_declared_bounds() -> None:
    """AC5: snippet and diagnostic outputs are truncated to their caps."""
    rendered = render_invisibles("x" * 10000)

    assert len(rendered) <= MAX_SNIPPET_CHARS
    assert rendered.endswith(("…", "..."))

    explanation = explain_difference("a" * 5000, "a" * 4999 + "b")

    assert len(explanation) <= MAX_DIAGNOSTIC_CHARS


def test_closest_candidate_scan_stops_at_the_line_cap() -> None:
    """AC5: a near miss beyond MAX_CANDIDATE_LINES is never reported."""
    lines = [
        f"unrelated_filler_entry_{index}" for index in range(MAX_CANDIDATE_LINES + 500)
    ]
    lines[MAX_CANDIDATE_LINES + 100] = TAB_VARIANT

    assert closest_candidate(lines, ANCHOR) is None


def test_explain_near_miss_names_a_tab_only_difference() -> None:
    """AC1: the tab-indented twin is reported with its line number and <TAB>."""
    lines = [
        "def compute():",
        "    values = [1, 2, 3]",
        TAB_VARIANT,
        "    return result",
    ]

    report = _near_miss(lines, ANCHOR)

    assert "3" in report.message
    assert "<TAB>" in report.message
    assert "\t" not in report.message


def test_explain_near_miss_counts_trailing_spaces() -> None:
    """AC1: each trailing space of the candidate yields one <SP> marker."""
    lines = [
        "def compute():",
        "    values = [1, 2, 3]  ",
        "    return values",
    ]

    report = _near_miss(lines, "    values = [1, 2, 3]")

    assert report.message.count("<SP>") == 2
    assert "2" in report.message


def test_explain_near_miss_names_a_non_breaking_space() -> None:
    """AC1: U+00A0 where the anchor has U+0020 is rendered as <NBSP>."""
    lines = [
        NBSP_VARIANT,
        "    return result",
    ]

    report = _near_miss(lines, ANCHOR)

    assert "<NBSP>" in report.message
    assert NBSP not in report.message
    assert "1" in report.message


def test_explain_near_miss_names_the_em_dash() -> None:
    """AC2: U+2014 is named, never dumped raw, with its line number."""
    lines = [
        "def render(total):",
        "    header = build_header()",
        "    footer = build_footer()",
        f"    label = 'total {EM_DASH} sum'",
    ]

    report = _near_miss(lines, "    label = 'total - sum'")

    assert "<EM DASH>" in report.message
    assert EM_DASH not in report.message
    assert "4" in report.message


def test_explain_near_miss_names_the_curly_apostrophe() -> None:
    """AC2: U+2019 is named, never dumped raw, with its line number."""
    lines = [
        "def render(total):",
        "    header = build_header()",
        "    footer = build_footer()",
        f'    message = "it{RIGHT_QUOTE}s done"',
    ]

    report = _near_miss(lines, '    message = "it\'s done"')

    assert "<RIGHT SINGLE QUOTATION MARK>" in report.message
    assert RIGHT_QUOTE not in report.message
    assert "4" in report.message


def test_explain_near_miss_names_the_box_drawing_dash() -> None:
    """AC2: U+2500 is named, never dumped raw, with its line number."""
    lines = [
        "def render(total):",
        "    header = build_header()",
        "    footer = build_footer()",
        f'    bar = "{BOX_HORIZONTAL}" * 10',
    ]

    report = _near_miss(lines, '    bar = "-" * 10')

    assert "<BOX DRAWINGS LIGHT HORIZONTAL>" in report.message
    assert BOX_HORIZONTAL not in report.message
    assert "4" in report.message


def test_explain_near_miss_reports_a_line_boundary_inside_the_anchor() -> None:
    """AC3: a single-line anchor spanning two file lines names <LF>."""
    lines = [
        "def parse(payload):",
        "    data = load(payload)",
        "    if not data:",
        "        return None",
        "    total = sum(item.value",
        "        for item in data)",
        "    return total",
        "",
    ]

    report = _near_miss(lines, lines[4] + lines[5])

    assert "5" in report.message
    assert "<LF>" in report.message


def test_explain_near_miss_reports_no_similar_line() -> None:
    """AC4: below the similarity threshold, no candidate is invented."""
    lines = [
        "The quick brown fox",
        "jumps over the lazy dog",
        "and then rests in the shade.",
    ]

    report = _near_miss(lines, "zzz_totally_absent()")

    assert isinstance(report, _diagnostics_attr("NearMiss"))
    assert report.candidate is None
    assert "no similar line" in report.message.lower()


def test_explain_near_miss_exposes_the_raw_candidate() -> None:
    """AC5: the candidate is the closest_candidate result, text unrendered."""
    lines = [
        "def compute():",
        "    values = [1, 2, 3]",
        NBSP_VARIANT,
        "    return result",
    ]

    report = _near_miss(lines, ANCHOR)

    assert report.candidate == closest_candidate(lines, ANCHOR)
    assert report.candidate is not None
    assert report.candidate.line == 3
    assert report.candidate.text == lines[2]
    assert NBSP in report.candidate.text


def test_explain_near_miss_truncates_a_very_long_candidate() -> None:
    """AC6: a 10 000-char candidate stays within MAX_DIAGNOSTIC_CHARS."""
    lines = [
        "alpha_header_entry",
        "beta_header_entry",
        "\t" + "z" * 10000,
    ]

    report = _near_miss(lines, "    " + "z" * 10000)

    assert len(report.message) <= MAX_DIAGNOSTIC_CHARS
    assert MAX_DIAGNOSTIC_CHARS == 400
    assert "3" in report.message


def test_format_match_lines_truncates_beyond_five_entries() -> None:
    """AC1: 12 match lines keep the first 5 and summarise the remainder."""
    hits = [3, 7, 11, 15, 19, 23, 27, 31, 35, 39, 43, 47]

    rendered = _diagnostics_attr("format_match_lines")(hits)

    assert "3, 7, 11, 15, 19" in rendered
    assert "(+7 more)" in rendered
    assert "47" not in rendered


def test_format_match_lines_keeps_five_or_fewer_untruncated() -> None:
    """AC1: five or fewer match lines render as a plain comma-joined list."""
    rendered = _diagnostics_attr("format_match_lines")([1, 2, 3, 4, 5])

    assert rendered == "1, 2, 3, 4, 5"
    assert "more)" not in rendered
