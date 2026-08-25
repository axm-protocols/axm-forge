"""Deterministic data layer for the on-disk byte report.

The MCP JSON transport decodes the payload once: an escape sequence written in a
tool argument reaches the tool as the literal character it denotes. These models
describe what a file actually contains on disk, so a write can be verified byte
for byte. They carry data only -- detection logic and I/O live elsewhere.

Every model below carries ``# type: ignore[explicit-any]`` on its class line for
the same reason as :mod:`axm_edit.models.check`: the pydantic mypy plugin
synthesizes ``__init__(**data: Any)``, which strict ``disallow_any_explicit``
rejects. The ignore is error-coded and local; no configuration is relaxed.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

__all__ = [
    "FileBytesReport",
    "LiteralEscapeOccurrence",
    "MismatchReport",
    "NonAsciiOccurrence",
]

Verdict = Literal[
    "ok",
    "literal_where_escaped_expected",
    "escaped_where_literal_expected",
    "mismatch",
    "decode_error",
]
"""Closed set of outcomes a byte-level inspection may report."""


class NonAsciiOccurrence(BaseModel):  # type: ignore[explicit-any]
    """A single non-ASCII character found in the decoded file content.

    Attributes:
        line: 1-indexed line where the character was found.
        col: 0-indexed column within that line.
        char: The character itself, verbatim.
        codepoint: Its ``U+XXXX`` notation.
        byte_offset: Offset of the character in the raw file bytes.
    """

    line: int
    col: int
    char: str
    codepoint: str
    byte_offset: int

    model_config = {"extra": "forbid"}


class LiteralEscapeOccurrence(BaseModel):  # type: ignore[explicit-any]
    """A literal escape sequence found verbatim in the file content.

    Attributes:
        line: 1-indexed line where the sequence starts.
        col: 0-indexed column within that line.
        sequence: The raw characters as they exist on disk -- a backslash
            followed by its escape body -- never decoded.
        byte_offset: Offset of the sequence in the raw file bytes.
    """

    line: int
    col: int
    sequence: str
    byte_offset: int

    model_config = {"extra": "forbid"}


class MismatchReport(BaseModel):  # type: ignore[explicit-any]
    """Where and how the on-disk bytes diverge from what was expected.

    Attributes:
        first_diff_offset: Byte offset of the first divergence.
        expected_repr: Printable rendering of the expected bytes.
        actual_repr: Printable rendering of the bytes actually on disk.
    """

    first_diff_offset: int
    expected_repr: str
    actual_repr: str

    model_config = {"extra": "forbid"}


class FileBytesReport(BaseModel):  # type: ignore[explicit-any]
    """Byte-level verdict for one file.

    The occurrence lists are deliberately bounded by the caller; the
    ``*_total`` counters keep that truncation explicit instead of silent.

    Attributes:
        sha256: Digest of the raw file bytes.
        size_bytes: Size of the file on disk.
        encoding_ok: Whether the bytes decoded cleanly as UTF-8.
        verdict: Outcome of the inspection.
        non_ascii: Bounded sample of non-ASCII characters found.
        literal_escapes: Bounded sample of literal escape sequences found.
        non_ascii_total: Untruncated count of non-ASCII characters.
        literal_escapes_total: Untruncated count of literal escapes.
        mismatch: Populated when the bytes diverge from what was expected.
        hint: Actionable remediation advice, when one applies.
    """

    sha256: str
    size_bytes: int
    encoding_ok: bool
    verdict: Verdict
    non_ascii: list[NonAsciiOccurrence] = Field(default_factory=list)
    literal_escapes: list[LiteralEscapeOccurrence] = Field(default_factory=list)
    non_ascii_total: int = 0
    literal_escapes_total: int = 0
    mismatch: MismatchReport | None = None
    hint: str | None = None

    model_config = {"extra": "forbid"}
