"""Unit tests for the anchor-miss diagnostic kernel.

Covers AC1 (invisible rendering), AC2 (difference explanation),
AC3/AC4 (closest candidate and its absence) and AC5 (hard bounds).
Everything is in-memory: no filesystem, no subprocess, no network.
"""

from __future__ import annotations

import re

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
ANCHOR = "    result = compute_total(values)"
TAB_VARIANT = "\tresult = compute_total(values)"


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
