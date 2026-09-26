"""Single owner of how a ``replace`` anchor is located in a file.

Both the engine (which applies edits) and the preflight (which predicts the
engine's verdict) resolve anchors through :func:`resolve_anchor`, so the
preflight can never block an anchor the engine would accept, nor let through
one the engine would refuse.

Resolution order, first hit wins:

1. the anchor as authored, then each normalized variant (smart quotes turned
   straight, wrapping double quotes stripped);
2. for each candidate, an exact line match, then an indent-normalized one;
3. with a ``line`` hint, the hint and ±5 lines around it first, then a
   full-file scan that only accepts a single match.

The whitespace model (:func:`common_ws_prefix`) is shared by indent
detection, dedenting and :func:`reindent`, so detection and re-application
always agree, tabs included.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Literal, TypeAlias

__all__ = [
    "AnchorMatch",
    "AnchorStatus",
    "anchor_matches_at",
    "common_ws_prefix",
    "old_line_count",
    "reindent",
    "resolve_anchor",
    "split_lines",
]

AnchorStatus: TypeAlias = Literal["found", "not_found", "ambiguous"]  # noqa: UP040 — radon crashes on `type` stmt

NORMALIZED_INDENT = "indent"
NORMALIZED_SMART_QUOTES = "smart_quotes"
NORMALIZED_WRAPPING_QUOTES = "wrapping_quotes"

_HINT_RADIUS = 5
_MIN_AMBIGUOUS_HITS = 2

_SMART_QUOTE_MAP: dict[str, str] = {
    "\u201c": '"',  # left double
    "\u201d": '"',  # right double
    "\u2018": "'",  # left single
    "\u2019": "'",  # right single
}

_MatchFn: TypeAlias = Callable[[int], bool]  # noqa: UP040 — radon crashes on `type` stmt
_Hit: TypeAlias = "tuple[int, str] | None"  # noqa: UP040


@dataclass(frozen=True)
class AnchorMatch:
    """Where, and how, an anchor resolved in a file.

    Attributes:
        status: ``found``, ``not_found``, or ``ambiguous`` (several matches
            and no ``line`` hint to pick one).
        line: 1-indexed start line when found.
        indent: Indent prefix to re-apply to ``new`` after an
            indent-normalized match, ``""`` otherwise.
        old: The anchor text that matched: the authored one, or the
            normalized variant.
        normalizations: What had to be normalized for the match, in order
            (``smart_quotes``, ``wrapping_quotes``, ``indent``); empty for a
            verbatim match.
        hits: Every candidate start line when ambiguous.
    """

    status: AnchorStatus
    line: int | None = None
    indent: str = ""
    old: str = ""
    normalizations: tuple[str, ...] = ()
    hits: tuple[int, ...] = ()


def split_lines(text: str) -> list[str]:
    """Split *text* after each ``\\n`` only, keeping the line ends.

    The one line model of every edit. Unlike :meth:`str.splitlines`, a form
    feed, vertical tab, file separator or U+2028 stays inside its line, so an
    anchor carrying one matches the file byte for byte.
    """
    pieces = text.split("\n")
    lines = [piece + "\n" for piece in pieces[:-1]]
    if pieces[-1]:
        lines.append(pieces[-1])
    return lines


def old_line_count(old: str) -> int:
    """Return the number of file lines spanned by *old*."""
    return old.rstrip("\n").count("\n") + 1


def common_ws_prefix(lines: Sequence[str]) -> str:
    """Return the literal longest common leading-whitespace prefix.

    The prefix is computed across *non-empty* lines and is treated as an
    opaque character sequence: tabs and spaces are compared by identity, so
    a tab never collapses into spaces (or vice versa).
    """
    non_empty = [ln for ln in lines if ln.strip()]
    if not non_empty:
        return ""
    leads = [ln[: len(ln) - len(ln.lstrip())] for ln in non_empty]
    prefix = leads[0]
    for lead in leads[1:]:
        limit = min(len(prefix), len(lead))
        i = 0
        while i < limit and prefix[i] == lead[i]:
            i += 1
        prefix = prefix[:i]
        if not prefix:
            break
    return prefix


def _dedent_block(text: str) -> str:
    """Strip the common whitespace prefix of *text*, then wrapping newlines."""
    raw_lines = split_lines(text)
    common = common_ws_prefix(raw_lines)
    if not common:
        return text.strip("\n")
    width = len(common)
    stripped = "".join((ln[width:] if ln.strip() else ln) for ln in raw_lines)
    return stripped.strip("\n")


def reindent(text: str, indent: str) -> str:
    """Dedent *text* fully, then prepend *indent* to each non-empty line.

    Relative indentation within the block is preserved; blank lines are kept
    verbatim.
    """
    raw_lines = split_lines(text)
    width = len(common_ws_prefix(raw_lines))
    return "".join(
        indent + (line[width:] if width else line) if line.strip() else line
        for line in raw_lines
    )


def _make_matchers(lines: Sequence[str], old: str) -> tuple[_MatchFn, _MatchFn, int]:
    """Build the exact and indent-normalized matchers of *old* on *lines*."""
    old_stripped = old.rstrip("\n")
    old_dedented = _dedent_block(old)
    num_lines = old_line_count(old)

    def block_at(start: int) -> str | None:
        if start < 1 or start + num_lines - 1 > len(lines):
            return None
        return "".join(lines[start - 1 : start - 1 + num_lines])

    def match_exact(start: int) -> bool:
        block = block_at(start)
        return block is not None and block.rstrip("\n") == old_stripped

    def match_dedented(start: int) -> bool:
        block = block_at(start)
        return block is not None and _dedent_block(block) == old_dedented

    return match_exact, match_dedented, num_lines


def _collect_hits(
    lines: Sequence[str], match_fn: _MatchFn, num_lines: int
) -> list[int]:
    """Return every 1-based line number where *match_fn* fires."""
    return [start for start in range(1, len(lines) - num_lines + 2) if match_fn(start)]


def _search(
    lines: Sequence[str],
    match_fn: _MatchFn,
    num_lines: int,
    hint_line: int | None,
) -> int | None:
    """Search near *hint_line* first, then accept a single file-wide match."""
    if hint_line is not None:
        for delta in range(_HINT_RADIUS + 1):
            for candidate in dict.fromkeys((hint_line - delta, hint_line + delta)):
                if match_fn(candidate):
                    return candidate
    hits = _collect_hits(lines, match_fn, num_lines)
    return hits[0] if len(hits) == 1 else None


def _find(
    lines: Sequence[str], old: str, hint_line: int | None
) -> tuple[int, str, bool] | None:
    """Locate *old*: exact first, then indent-normalized.

    Returns:
        ``(line, indent, dedented)`` on a match, ``None`` otherwise.
    """
    match_exact, match_dedented, num_lines = _make_matchers(lines, old)
    line = _search(lines, match_exact, num_lines, hint_line)
    if line is not None:
        return line, "", False
    line = _search(lines, match_dedented, num_lines, hint_line)
    if line is None:
        return None
    block = lines[line - 1 : line - 1 + num_lines]
    return line, common_ws_prefix(block), True


def _variants(old: str) -> Iterator[tuple[str, tuple[str, ...]]]:
    """Yield *old*, then each normalized variant with what it normalized."""
    yield old, ()
    straight = old
    for smart, plain in _SMART_QUOTE_MAP.items():
        straight = straight.replace(smart, plain)
    if straight != old:
        yield straight, (NORMALIZED_SMART_QUOTES,)
    if old.startswith('"') and old.endswith('"') and len(old) > len('""'):
        yield old[1:-1], (NORMALIZED_WRAPPING_QUOTES,)


def _all_match_lines(lines: Sequence[str], old: str) -> list[int]:
    """Return all 1-based lines matching *old* (exact, else indent-normalized)."""
    match_exact, match_dedented, num_lines = _make_matchers(lines, old)
    exact_hits = _collect_hits(lines, match_exact, num_lines)
    if exact_hits:
        return exact_hits
    return _collect_hits(lines, match_dedented, num_lines)


def anchor_matches_at(lines: Sequence[str], old: str, line: int) -> bool:
    """Tell whether *old* still matches at *line*, exactly or indent-normalized."""
    match_exact, match_dedented, _ = _make_matchers(lines, old)
    return match_exact(line) or match_dedented(line)


def resolve_anchor(
    lines: Sequence[str], old: str, hint_line: int | None
) -> AnchorMatch:
    """Resolve *old* in *lines*, the file split by :func:`split_lines`.

    Args:
        lines: File content as read, split by :func:`split_lines`.
        old: The anchor as authored.
        hint_line: Optional 1-indexed line hint.

    Returns:
        The match, or why there is none: ``ambiguous`` when the authored
        anchor matches several lines and no hint picks one, ``not_found``
        otherwise.
    """
    for variant, normalized in _variants(old):
        found = _find(lines, variant, hint_line)
        if found is not None:
            line, indent, dedented = found
            extra = (NORMALIZED_INDENT,) if dedented else ()
            return AnchorMatch(
                status="found",
                line=line,
                indent=indent,
                old=variant,
                normalizations=normalized + extra,
            )
    hits = _all_match_lines(lines, old)
    if hint_line is None and len(hits) >= _MIN_AMBIGUOUS_HITS:
        return AnchorMatch(status="ambiguous", old=old, hits=tuple(hits))
    return AnchorMatch(status="not_found", old=old)
