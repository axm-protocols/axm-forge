"""Byte-exact reporting on a payload already read from disk.

Pure, in-memory helpers: every function receives bytes or decoded text and
returns a report. No file, network or process boundary is crossed here — the
I/O belongs to the calling AXMTool.

The module implements lesson L4: an escape sequence present *on disk* is a run
of ASCII characters (``chr(92) + "u00e9"`` is six characters), not a single
codepoint. Comparing the two requires looking at the bytes, never at a value
that Python already decoded.
"""

from __future__ import annotations

import hashlib
import string
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Literal

from axm_edit.core.diagnostics import _first_difference

__all__ = [
    "MAX_OCCURRENCES",
    "ByteReport",
    "LiteralEscape",
    "MismatchDetail",
    "NonAsciiOccurrence",
    "Verdict",
    "build_hint",
    "build_report",
    "compare_expected",
    "decide_verdict",
    "scan_literal_escapes",
    "scan_non_ascii",
]

type Verdict = Literal[
    "ok",
    "decode_error",
    "mismatch",
    "literal_where_escaped_expected",
    "escaped_where_literal_expected",
]

MAX_OCCURRENCES = 50
"""Upper bound on every occurrence list carried by a report."""

MISMATCH_WINDOW = 40
"""Characters kept on each side of the first divergence."""

_ASCII_MAX = 127
_BACKSLASH = chr(92)
_ESCAPE_WIDTHS = {"x": 2, "u": 4, "U": 8}

_HINT_LITERAL = (
    "L4 : le fichier contient du non-ASCII litteral alors que l'appelant "
    "attendait des sequences echappees. Le transport MCP a deja decode la "
    "charge utile une fois ; il faut doubler l'echappement au site d'appel "
    "MCP (envoyer "
    + _BACKSLASH * 2
    + "u00e9 pour obtenir "
    + _BACKSLASH
    + "u00e9 sur disque)."
)
_HINT_ESCAPED = (
    "L4 (cas symetrique) : le fichier contient des sequences d'echappement "
    "textuelles alors que l'appelant attendait des caracteres litteraux. "
    "L'echappement a ete doubler une fois de trop au site d'appel MCP ; "
    "envoyer le caractere litteral."
)
_HINT_MISMATCH = (
    "Le contenu sur disque diverge du contenu attendu : comparer les reprs "
    "echappes autour de first_diff_offset."
)
_HINT_DECODE = (
    "Les octets ne sont pas decodables en UTF-8 : le rapport a ete produit "
    "avec un decodage tolerant (caracteres de remplacement)."
)
_HINTS: dict[str, str] = {
    "literal_where_escaped_expected": _HINT_LITERAL,
    "escaped_where_literal_expected": _HINT_ESCAPED,
    "mismatch": _HINT_MISMATCH,
    "decode_error": _HINT_DECODE,
}


@dataclass(frozen=True, slots=True)
class NonAsciiOccurrence:
    """A single non-ASCII character located in the decoded text."""

    line: int
    col: int
    char: str
    codepoint: str
    byte_offset: int


@dataclass(frozen=True, slots=True)
class LiteralEscape:
    """An escape sequence present verbatim, as ASCII text, on disk."""

    offset: int
    sequence: str


@dataclass(frozen=True, slots=True)
class MismatchDetail:
    """Localised divergence between the expected and the actual content."""

    first_diff_offset: int
    expected_repr: str
    actual_repr: str


@dataclass(frozen=True, slots=True)
class ByteReport:
    """Byte-exact verdict on a payload, with its supporting evidence."""

    sha256: str
    size: int
    encoding_ok: bool
    verdict: Verdict
    hint: str
    non_ascii_total: int = 0
    literal_escapes_total: int = 0
    mismatch: MismatchDetail | None = None
    non_ascii: list[NonAsciiOccurrence] = field(default_factory=list)
    literal_escapes: list[LiteralEscape] = field(default_factory=list)


def scan_non_ascii(text: str, limit: int = MAX_OCCURRENCES) -> list[NonAsciiOccurrence]:
    """Locate non-ASCII characters, 1-based line/col, UTF-8 byte offset.

    At most ``limit`` occurrences are returned; the offset counts UTF-8 bytes
    from the start of the text, not characters.
    """
    occurrences, _ = _bounded(_iter_non_ascii(text), limit)
    return occurrences


def scan_literal_escapes(
    text: str, limit: int = MAX_OCCURRENCES
) -> list[LiteralEscape]:
    """Locate escape sequences written as plain ASCII text on disk.

    Only the numeric forms are reported (``\\xNN``, ``\\uNNNN``,
    ``\\UNNNNNNNN``); each sequence is kept verbatim.
    """
    escapes, _ = _bounded(_iter_literal_escapes(text), limit)
    return escapes


def compare_expected(expected: str, actual: str) -> MismatchDetail | None:
    """Return the first divergence between two texts, ``None`` if equal."""
    offset = _first_difference(expected, actual)
    if offset is None:
        return None
    start = max(0, offset - MISMATCH_WINDOW)
    end = offset + MISMATCH_WINDOW
    return MismatchDetail(
        first_diff_offset=offset,
        expected_repr=ascii(expected[start:end]),
        actual_repr=ascii(actual[start:end]),
    )


def decide_verdict(
    encoding_ok: bool,
    mismatch: MismatchDetail | None,
    non_ascii_total: int,
    literal_escapes_total: int,
    expect_escaped: bool | None = None,
) -> Verdict:
    """Pick the verdict under a strict priority.

    Decode error first, then divergence, then the escaping inconsistency, and
    ``ok`` otherwise. Without an explicit ``expect_escaped`` contract no
    escaping verdict is ever emitted.
    """
    if not encoding_ok:
        return "decode_error"
    if mismatch is not None:
        return "mismatch"
    if expect_escaped is None:
        return "ok"
    if expect_escaped and non_ascii_total:
        return "literal_where_escaped_expected"
    if not expect_escaped and literal_escapes_total:
        return "escaped_where_literal_expected"
    return "ok"


def build_hint(verdict: Verdict) -> str:
    """Return an actionable message for ``verdict`` (empty when ``ok``)."""
    return _HINTS.get(verdict, "")


def build_report(
    data: bytes,
    expected: str | None = None,
    expect_escaped: bool | None = None,
) -> ByteReport:
    """Build the byte-exact report for ``data``.

    ``data`` is hashed as-is, decoded strictly to determine ``encoding_ok``,
    then decoded tolerantly so a readable report can be produced even for
    undecodable bytes. No exception escapes this function.
    """
    encoding_ok = _is_utf8(data)
    text = data.decode("utf-8", errors="replace")
    non_ascii, non_ascii_total = _bounded(_iter_non_ascii(text), MAX_OCCURRENCES)
    escapes, escapes_total = _bounded(_iter_literal_escapes(text), MAX_OCCURRENCES)
    mismatch = None if expected is None else compare_expected(expected, text)
    verdict = decide_verdict(
        encoding_ok, mismatch, non_ascii_total, escapes_total, expect_escaped
    )
    return ByteReport(
        sha256=hashlib.sha256(data).hexdigest(),
        size=len(data),
        encoding_ok=encoding_ok,
        verdict=verdict,
        hint=build_hint(verdict),
        non_ascii_total=non_ascii_total,
        literal_escapes_total=escapes_total,
        mismatch=mismatch,
        non_ascii=non_ascii,
        literal_escapes=escapes,
    )


def _is_utf8(data: bytes) -> bool:
    """Tell whether ``data`` decodes strictly as UTF-8."""
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _bounded[T](items: Iterable[T], limit: int) -> tuple[list[T], int]:
    """Keep at most ``limit`` items while counting the real total."""
    kept: list[T] = []
    total = 0
    for item in items:
        total += 1
        if len(kept) < limit:
            kept.append(item)
    return kept, total


def _iter_non_ascii(text: str) -> Iterator[NonAsciiOccurrence]:
    """Yield every non-ASCII character with its position."""
    line = 1
    col = 1
    byte_offset = 0
    for char in text:
        if ord(char) > _ASCII_MAX:
            yield NonAsciiOccurrence(
                line=line,
                col=col,
                char=char,
                codepoint=f"U+{ord(char):04X}",
                byte_offset=byte_offset,
            )
        byte_offset += len(char.encode("utf-8"))
        line, col = (line + 1, 1) if char == "\n" else (line, col + 1)


def _iter_literal_escapes(text: str) -> Iterator[LiteralEscape]:
    """Yield escape sequences present verbatim as ASCII text."""
    index = 0
    length = len(text)
    while index < length:
        if text[index] != _BACKSLASH:
            index += 1
            continue
        sequence = _match_escape(text, index)
        if sequence is None:
            index += 2 if text[index + 1 : index + 2] == _BACKSLASH else 1
            continue
        yield LiteralEscape(offset=index, sequence=sequence)
        index += len(sequence)


def _match_escape(text: str, index: int) -> str | None:
    """Return the numeric escape sequence starting at ``index``, if any."""
    width = _ESCAPE_WIDTHS.get(text[index + 1 : index + 2])
    if width is None:
        return None
    digits = text[index + 2 : index + 2 + width]
    if len(digits) != width or not _all_hex(digits):
        return None
    return text[index : index + 2 + width]


def _all_hex(digits: Sequence[str]) -> bool:
    """Tell whether every character is a hexadecimal digit."""
    return all(char in string.hexdigits for char in digits)
