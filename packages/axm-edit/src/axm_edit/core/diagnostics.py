"""Pure, bounded diagnostics for anchor mismatches.

When an anchor fails to match, the caller needs to know *why*: a tab where
spaces were expected, a trailing space run, a non-breaking space, an em dash
instead of a hyphen, or simply the wrong line. This module answers that
question with side-effect-free helpers: no filesystem, no subprocess, no
network. Inputs are already-read lines plus the anchor string.

Every output is bounded (``MAX_SNIPPET_CHARS``, ``MAX_DIAGNOSTIC_CHARS``) and
every scan is bounded (``MAX_CANDIDATE_LINES``) so a pathological input can
neither blow up the message nor the runtime.
"""

from __future__ import annotations

import difflib
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

__all__ = [
    "MAX_CANDIDATE_LINES",
    "MAX_DIAGNOSTIC_CHARS",
    "MAX_SNIPPET_CHARS",
    "SIMILARITY_THRESHOLD",
    "Candidate",
    "NearMiss",
    "closest_candidate",
    "explain_difference",
    "explain_near_miss",
    "render_invisibles",
]

#: Hard cap on the number of scanned lines when looking for a near miss.
MAX_CANDIDATE_LINES = 5000
#: Hard cap on a single rendered snippet, ellipsis marker included.
MAX_SNIPPET_CHARS = 120
#: Hard cap on a whole explanation string.
MAX_DIAGNOSTIC_CHARS = 400
#: Minimum similarity ratio below which no candidate is reported at all.
SIMILARITY_THRESHOLD = 0.7

_ELLIPSIS = "..."
_NBSP = chr(0xA0)
_TRAILING_SPACE_MARKER = "<SP>"
_END_MARKER = "<END>"
_NO_CANDIDATE_MESSAGE = "no similar line found near the anchor"
_MARKERS = {
    "\t": "<TAB>",
    "\r": "<CR>",
    "\n": "<LF>",
    _NBSP: "<NBSP>",
}
_PRINTABLE_ASCII_MIN = 0x20
_PRINTABLE_ASCII_MAX = 0x7E


@dataclass(frozen=True, slots=True)
class Candidate:
    """A near-miss window found in the scanned lines.

    Attributes:
        line: 1-based line number where the window starts.
        ratio: similarity ratio against the anchor, in ``[0.0, 1.0]``.
        text: the raw window text, terminators excluded.
    """

    line: int
    ratio: float
    text: str


@dataclass(frozen=True, slots=True)
class NearMiss:
    """A rendered explanation for an anchor that matched nothing.

    Attributes:
        candidate: the closest window found, ``None`` when none is similar
            enough; exposed exactly as :func:`closest_candidate` produced it,
            so ``text`` stays raw and unrendered.
        message: a single bounded line naming the difference, every invisible
            or non-ASCII character replaced by its marker.
    """

    candidate: Candidate | None
    message: str


def _name_char(char: str) -> str:
    """Return the Unicode name of ``char``, falling back to ``<U+XXXX>``."""
    try:
        return f"<{unicodedata.name(char)}>"
    except ValueError:
        return f"<U+{ord(char):04X}>"


def _render_char(char: str) -> str:
    """Render a single character, naming everything that is not plain ASCII."""
    marker = _MARKERS.get(char)
    if marker is not None:
        return marker
    if _PRINTABLE_ASCII_MIN <= ord(char) <= _PRINTABLE_ASCII_MAX:
        return char
    return _name_char(char)


def _render_body(body: str) -> str:
    """Render one line body, marking its trailing space run explicitly."""
    stripped = body.rstrip(" ")
    trailing = len(body) - len(stripped)
    rendered = "".join(_render_char(char) for char in stripped)
    return rendered + _TRAILING_SPACE_MARKER * trailing


def _truncate(text: str, limit: int) -> str:
    """Clamp ``text`` to ``limit`` characters, ellipsis marker included."""
    if len(text) <= limit:
        return text
    return text[: limit - len(_ELLIPSIS)] + _ELLIPSIS


def render_invisibles(text: str) -> str:
    """Render ``text`` with every invisible or non-ASCII character named.

    Tabs become ``<TAB>``, a trailing space run becomes one ``<SP>`` marker per
    space, U+00A0 becomes ``<NBSP>``, line terminators become ``<CR>``/``<LF>``
    and any other non-ASCII character becomes its Unicode name (or the
    ``<U+XXXX>`` fallback). Ordinary printable ASCII is passed through
    untouched. The result never exceeds ``MAX_SNIPPET_CHARS``.
    """
    rendered: list[str] = []
    for piece in text.splitlines(keepends=True):
        body = piece.rstrip("\r\n")
        terminator = piece[len(body) :]
        rendered.append(_render_body(body))
        rendered.extend(_render_char(char) for char in terminator)
    return _truncate("".join(rendered), MAX_SNIPPET_CHARS)


def _first_difference(expected: str, actual: str) -> int | None:
    """Return the 0-based index of the first difference, ``None`` if equal."""
    for index, (left, right) in enumerate(zip(expected, actual, strict=False)):
        if left != right:
            return index
    if len(expected) != len(actual):
        return min(len(expected), len(actual))
    return None


def _describe_char(text: str, index: int) -> str:
    """Name the character at ``index``, or mark the end of the string."""
    if index >= len(text):
        return _END_MARKER
    char = text[index]
    if char == " ":
        return _TRAILING_SPACE_MARKER
    return _render_char(char)


def explain_difference(expected: str, actual: str) -> str:
    """Explain, on a single bounded line, how ``actual`` differs from ``expected``.

    The message names the 1-based column of the first difference, the two
    offending characters (non-ASCII punctuation is routed through the Unicode
    naming helper) and both sides rendered by :func:`render_invisibles`. The
    result never exceeds ``MAX_DIAGNOSTIC_CHARS``.
    """
    column = _first_difference(expected, actual)
    if column is None:
        return "no difference: both sides are identical"
    message = (
        f"first difference at column {column + 1}: "
        f"expected {_describe_char(expected, column)} "
        f"vs actual {_describe_char(actual, column)} "
        f"| expected {render_invisibles(expected)} "
        f"| actual {render_invisibles(actual)}"
    )
    return _truncate(message, MAX_DIAGNOSTIC_CHARS)


def closest_candidate(lines: Sequence[str], old: str) -> Candidate | None:
    """Return the line window closest to the ``old`` anchor, or ``None``.

    The scan slides a window of the anchor's line count over the first
    ``MAX_CANDIDATE_LINES`` lines and keeps the best similarity ratio. A window
    below ``SIMILARITY_THRESHOLD`` is never reported: no best-effort guess.
    Ties are resolved deterministically in favour of the lowest 1-based line
    number, thanks to the strictly-greater comparison.
    """
    anchor_lines = old.splitlines() or [old]
    span = len(anchor_lines)
    scanned = lines[:MAX_CANDIDATE_LINES]
    if span == 0 or len(scanned) < span:
        return None

    matcher: difflib.SequenceMatcher[str] = difflib.SequenceMatcher(autojunk=False)
    matcher.set_seq2("\n".join(anchor_lines))
    best: Candidate | None = None
    for start in range(len(scanned) - span + 1):
        window = "\n".join(scanned[start : start + span])
        matcher.set_seq1(window)
        if matcher.real_quick_ratio() < SIMILARITY_THRESHOLD:
            continue
        if matcher.quick_ratio() < SIMILARITY_THRESHOLD:
            continue
        ratio = matcher.ratio()
        if ratio < SIMILARITY_THRESHOLD:
            continue
        if best is None or ratio > best.ratio:
            best = Candidate(line=start + 1, ratio=ratio, text=window)
    return best


def _boundary_line(lines: Sequence[str], old: str) -> int | None:
    """Return the 1-based line whose join with the next one equals ``old``.

    A single-line anchor that swallowed a line break matches two consecutive
    file lines concatenated; the first of them is the line to report.
    """
    if not old or "\n" in old or "\r" in old:
        return None
    scanned = lines[:MAX_CANDIDATE_LINES]
    for index in range(len(scanned) - 1):
        if scanned[index] + scanned[index + 1] == old:
            return index + 1
    return None


def _boundary_message(lines: Sequence[str], line: int) -> str:
    """Explain that the anchor straddles the boundary starting at ``line``."""
    joined = "\n".join(lines[line - 1 : line + 1])
    return (
        f"near miss at line {line}: the anchor spans a line boundary "
        f"| file {render_invisibles(joined)}"
    )


def _candidate_message(candidate: Candidate, old: str) -> str:
    """Contrast the anchor with ``candidate``, every invisible named."""
    return (
        f"near miss at line {candidate.line}: "
        f"anchor {render_invisibles(old)} "
        f"| line {render_invisibles(candidate.text)}"
    )


def explain_near_miss(lines: Sequence[str], old: str) -> NearMiss:
    """Assemble the near-miss report for an ``old`` anchor that matched nothing.

    Three branches, in order: the anchor swallowed a line break (the message
    names the first of the two joined lines and carries the ``<LF>`` marker);
    a similar window exists (the message names its 1-based line and contrasts
    both sides through :func:`render_invisibles`, so a tab, a trailing space
    run, a non-breaking space or a Unicode punctuation swap is named instead
    of being dumped raw); or nothing is similar enough, in which case the
    candidate is ``None`` and the message says so explicitly.

    The returned candidate is the one :func:`closest_candidate` produced,
    unchanged, and the message never exceeds ``MAX_DIAGNOSTIC_CHARS``.
    """
    candidate = closest_candidate(lines, old)
    boundary = _boundary_line(lines, old)
    if boundary is not None:
        bounded = _truncate(_boundary_message(lines, boundary), MAX_DIAGNOSTIC_CHARS)
        return NearMiss(candidate=candidate, message=bounded)
    if candidate is None:
        return NearMiss(candidate=None, message=_NO_CANDIDATE_MESSAGE)
    bounded = _truncate(_candidate_message(candidate, old), MAX_DIAGNOSTIC_CHARS)
    return NearMiss(candidate=candidate, message=bounded)
