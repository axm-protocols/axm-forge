"""Unit tests for :mod:`axm_edit.core.byte_report` (pure, in-memory)."""

from __future__ import annotations

import hashlib

from axm_edit.core.byte_report import build_report, scan_non_ascii

BACKSLASH = chr(92)


def test_literal_non_ascii_where_escaped_was_expected() -> None:
    """AC1: literal non-ASCII while the caller expected escaped payload."""
    report = build_report(
        "héllo".encode(),
        expected=None,
        expect_escaped=True,
    )

    assert report.verdict == "literal_where_escaped_expected"
    assert isinstance(report.hint, str)
    assert report.hint != ""
    assert "doubler" in report.hint
    assert "MCP" in report.hint


def test_textual_escape_where_literal_was_expected() -> None:
    """AC2: six-char textual escape while the caller expected a literal."""
    payload = BACKSLASH + "u00e9"

    report = build_report(
        payload.encode(),
        expected=None,
        expect_escaped=False,
    )

    assert report.verdict == "escaped_where_literal_expected"
    assert report.literal_escapes
    first = report.literal_escapes[0]
    assert len(first.sequence) == 6
    assert first.sequence.startswith(BACKSLASH + "u")


def test_matching_content_yields_ok_and_reproducible_sha256() -> None:
    """AC3: identical content gives ok, no mismatch and a stable digest."""
    data = b"plain ascii"

    first = build_report(data, expected="plain ascii", expect_escaped=False)
    second = build_report(data, expected="plain ascii", expect_escaped=False)

    assert first.verdict == "ok"
    assert first.mismatch is None
    assert first.sha256 == hashlib.sha256(data).hexdigest()
    assert second.sha256 == first.sha256


def test_mismatch_reports_offset_and_ascii_only_reprs() -> None:
    """AC4: divergence localised at offset 3 with pure-ASCII reprs."""
    report = build_report(
        b"abcdef",
        expected="abcXef",
        expect_escaped=False,
    )

    assert report.verdict == "mismatch"
    assert report.mismatch is not None
    assert report.mismatch.first_diff_offset == 3
    assert all(ord(char) < 128 for char in report.mismatch.expected_repr)
    assert all(ord(char) < 128 for char in report.mismatch.actual_repr)


def test_undecodable_bytes_report_decode_error_without_raising() -> None:
    """AC5: undecodable UTF-8 bytes yield decode_error, never an exception."""
    data = bytes([0xFF, 0xFE, 0x61, 0x62, 0x63])

    report = build_report(data, expected=None, expect_escaped=False)

    assert report.encoding_ok is False
    assert report.verdict == "decode_error"


def test_non_ascii_occurrences_capped_while_total_is_kept() -> None:
    """AC6: occurrences truncated to 50, real total kept in the counter."""
    text = "é" * 120

    report = build_report(text.encode(), expected=None, expect_escaped=False)

    assert len(report.non_ascii) == 50
    assert report.non_ascii_total == 120


def test_scan_non_ascii_positions_use_utf8_byte_offset() -> None:
    """AC7: 1-based line/col, codepoint label and UTF-8 byte offset."""
    occurrences = scan_non_ascii("a\nbé", 50)

    assert len(occurrences) == 1
    occurrence = occurrences[0]
    assert occurrence.line == 2
    assert occurrence.col == 2
    assert occurrence.char == "é"
    assert occurrence.codepoint == "U+00E9"
    assert occurrence.byte_offset == 3
