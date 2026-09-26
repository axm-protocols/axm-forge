"""Unit tests for axm_edit.core.anchor_match (pure, no I/O)."""

from __future__ import annotations

from axm_edit.core.anchor_match import resolve_anchor, split_lines

LINES = split_lines("def f():\n    x = 1\n    return x\n\n\ndef g():\n    return x\n")


class TestSplitLines:
    """The single line model splits on ``\\n`` only."""

    def test_form_feed_stays_inside_its_line(self) -> None:
        """Unlike str.splitlines, a form feed is not a line break."""
        assert split_lines("a\x0cb\nc\n") == ["a\x0cb\n", "c\n"]

    def test_last_line_without_newline_is_kept(self) -> None:
        """A missing final newline leaves a bare last line."""
        assert split_lines("a\nb") == ["a\n", "b"]

    def test_empty_text_has_no_line(self) -> None:
        """An empty file has no line at all."""
        assert split_lines("") == []


class TestResolveAnchor:
    """Statuses and normalizations reported by the shared resolver."""

    def test_verbatim_match_has_no_normalization(self) -> None:
        """An exact anchor resolves with an empty normalization list."""
        match = resolve_anchor(LINES, "    x = 1", None)

        assert (match.status, match.line, match.normalizations) == ("found", 2, ())

    def test_missing_indent_is_an_indent_normalization(self) -> None:
        """A dedented anchor resolves and carries the file's indent."""
        match = resolve_anchor(LINES, "x = 1", None)

        assert (match.status, match.line, match.indent) == ("found", 2, "    ")
        assert match.normalizations == ("indent",)

    def test_smart_quotes_are_a_normalization(self) -> None:
        """Curly quotes resolve against straight ones, and say so."""
        lines = split_lines('s = "a"\n')

        match = resolve_anchor(lines, f"s = {chr(0x201C)}a{chr(0x201D)}", None)

        assert match.status == "found"
        assert match.old == 's = "a"'
        assert match.normalizations == ("smart_quotes",)

    def test_unhinted_duplicate_is_ambiguous_with_every_line(self) -> None:
        """Several matches and no hint: ambiguous, candidates listed."""
        match = resolve_anchor(LINES, "    return x", None)

        assert (match.status, match.hits) == ("ambiguous", (3, 7))

    def test_hint_picks_one_duplicate(self) -> None:
        """A hint near one candidate resolves the ambiguity."""
        match = resolve_anchor(LINES, "    return x", 7)

        assert (match.status, match.line) == ("found", 7)

    def test_line_substring_is_not_found(self) -> None:
        """Anchors match whole lines, never a fragment of one."""
        match = resolve_anchor(LINES, "x = 1\n    return", None)

        assert match.status == "not_found"
