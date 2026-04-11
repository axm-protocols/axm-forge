"""Strip-html-comments strategy — remove HTML comments from markdown/text."""

from __future__ import annotations

import re

from axm_smelt.core.models import Format, SmeltContext
from axm_smelt.strategies.base import SmeltStrategy

__all__ = ["StripHtmlCommentsStrategy"]

_FENCED_BLOCK_RE = re.compile(r"(`{3,})[\s\S]*?\1", re.MULTILINE)
_HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
_MULTI_BLANK_RE = re.compile(r"\n{3,}")

_APPLICABLE_FORMATS = frozenset({Format.MARKDOWN, Format.TEXT})


def _strip_comments(text: str) -> str:
    """Remove HTML comments and clean up surrounding whitespace."""
    result: list[str] = []
    last_end = 0

    for m in _HTML_COMMENT_RE.finditer(text):
        start, end = m.start(), m.end()
        result.append(text[last_end:start])

        # If comment is preceded by only whitespace on its line, consume that
        # If comment is followed by a newline, consume it
        # This avoids leaving blank lines where comments were
        seg = result[-1] if result else ""
        if seg.endswith("\n") or start == 0:
            # Comment starts at beginning of a line
            if end < len(text) and text[end] == "\n":
                end += 1  # consume trailing newline

        last_end = end

    result.append(text[last_end:])
    return "".join(result)


class StripHtmlCommentsStrategy(SmeltStrategy):
    """Remove HTML comments from markdown and plain-text content."""

    @property
    def name(self) -> str:
        return "strip_html_comments"

    @property
    def category(self) -> str:
        return "cosmetic"

    def apply(self, ctx: SmeltContext) -> SmeltContext:
        """Strip HTML comments outside fenced code blocks."""
        if ctx.format not in _APPLICABLE_FORMATS:
            return ctx

        text = ctx.text

        # Protect fenced code blocks with placeholders
        blocks: list[str] = []

        def _save_block(m: re.Match[str]) -> str:
            idx = len(blocks)
            blocks.append(m.group(0))
            return f"\x00CODEBLOCK{idx}\x00"

        stripped = _FENCED_BLOCK_RE.sub(_save_block, text)

        # Remove HTML comments
        result = _strip_comments(stripped)

        # Clean up runs of blank lines left by removal
        result = _MULTI_BLANK_RE.sub("\n\n", result)

        # Restore code blocks
        for idx, block in enumerate(blocks):
            result = result.replace(f"\x00CODEBLOCK{idx}\x00", block)

        if result == text:
            return ctx
        return SmeltContext(text=result, format=ctx.format)
