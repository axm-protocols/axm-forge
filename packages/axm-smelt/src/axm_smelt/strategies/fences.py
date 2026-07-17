"""Shared fenced-code-block primitive for markdown-aware strategies.

Factors out the backreference fence regex that was previously duplicated
across :mod:`collapse_whitespace`, :mod:`strip_html_comments` and
:mod:`compact_tables`.  Capturing the opening backtick run and closing on
the exact same length means a 4-backtick fence is not closed by an inner
3-backtick line.
"""

from __future__ import annotations

import re

__all__ = ["FENCED_BLOCK_RE", "fenced_line_indices"]

# ``\1`` forces the closing fence to match the opening backtick run length
# exactly, so ```` blocks survive inner ``` lines.
FENCED_BLOCK_RE = re.compile(r"(`{3,})[\s\S]*?\1", re.MULTILINE)


def fenced_line_indices(text: str) -> set[int]:
    """Return indices of lines that fall inside a fenced code block.

    Lines are indexed as produced by ``text.split("\\n")``.  Both fence
    delimiter lines and the content between them are included.
    """
    fenced: set[int] = set()
    for match in FENCED_BLOCK_RE.finditer(text):
        start = text.count("\n", 0, match.start())
        end = text.count("\n", 0, match.end())
        fenced.update(range(start, end + 1))
    return fenced
