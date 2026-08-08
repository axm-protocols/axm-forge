"""Unit tests for :mod:`axm_edit.models.file_bytes` (pure models, no I/O)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from axm_edit.models import file_bytes as file_bytes_module
from axm_edit.models.file_bytes import (
    FileBytesReport,
    LiteralEscapeOccurrence,
    MismatchReport,
    NonAsciiOccurrence,
)

BACKSLASH = chr(92)


def test_public_models_are_importable_and_all_is_exact() -> None:
    """AC1: the four models are importable and ``__all__`` lists exactly them."""
    assert set(file_bytes_module.__all__) == {
        "FileBytesReport",
        "LiteralEscapeOccurrence",
        "MismatchReport",
        "NonAsciiOccurrence",
    }


def test_non_ascii_occurrence_serialises_its_five_fields() -> None:
    """AC2: ``NonAsciiOccurrence.model_dump()`` yields exactly the five fields."""
    occurrence = NonAsciiOccurrence(
        line=3,
        col=12,
        char=chr(0xE9),
        codepoint="U+00E9",
        byte_offset=41,
    )

    assert occurrence.model_dump() == {
        "line": 3,
        "col": 12,
        "char": chr(0xE9),
        "codepoint": "U+00E9",
        "byte_offset": 41,
    }


def test_literal_escape_occurrence_keeps_sequence_verbatim() -> None:
    """AC3: ``sequence`` keeps the six raw characters, with no decoding."""
    occurrence = LiteralEscapeOccurrence(
        line=1,
        col=0,
        sequence=BACKSLASH + "u00e9",
        byte_offset=0,
    )

    assert len(occurrence.sequence) == 6
    assert occurrence.sequence[0] == BACKSLASH
    assert occurrence.sequence[1] == "u"


def test_mismatch_report_exposes_offset_and_two_str_reprs() -> None:
    """AC4: ``MismatchReport`` carries an int offset and two ``str`` reprs."""
    report = MismatchReport(
        first_diff_offset=7,
        expected_repr=BACKSLASH + "u00e9",
        actual_repr=chr(0xE9),
    )

    assert report.first_diff_offset == 7
    assert isinstance(report.expected_repr, str)
    assert isinstance(report.actual_repr, str)


def test_file_bytes_report_applies_empty_defaults() -> None:
    """AC5: optional fields default to empty lists, zero counters and None."""
    report = FileBytesReport(
        sha256="0" * 64,
        size_bytes=128,
        encoding_ok=True,
        verdict="ok",
    )

    assert report.non_ascii == []
    assert report.literal_escapes == []
    assert report.non_ascii_total == 0
    assert report.literal_escapes_total == 0
    assert report.mismatch is None
    assert report.hint is None


def test_file_bytes_report_rejects_verdict_outside_enumeration() -> None:
    """AC6: ``verdict`` only accepts the five declared literal values."""
    with pytest.raises(ValidationError):
        FileBytesReport(
            sha256="0" * 64,
            size_bytes=128,
            encoding_ok=True,
            verdict="probably_fine",
        )
