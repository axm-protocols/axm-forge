"""Collapse-whitespace strategy — reduce redundant blank lines and trailing spaces."""

from __future__ import annotations

import re

from axm_smelt.core.models import Format, SmeltContext
from axm_smelt.strategies.base import SmeltStrategy

__all__ = ["CollapseWhitespaceStrategy"]

_FENCED_BLOCK_RE = re.compile(r"(`{3,})[\s\S]*?\1", re.MULTILINE)
_MULTI_BLANK_RE = re.compile(r"\n{3,}")
_TRAILING_WS_RE = re.compile(r"[ \t]+$", re.MULTILINE)

_STRUCTURED_FORMATS = frozenset(
    {Format.JSON, Format.YAML, Format.XML, Format.TOML, Format.CSV}
)


class CollapseWhitespaceStrategy(SmeltStrategy):
    """Collapse consecutive blank lines and strip trailing whitespace."""

    @property
    def name(self) -> str:
        """Strategy identifier used in the registry."""
        return "collapse_whitespace"

    @property
    def category(self) -> str:
        """Strategy category (``whitespace``)."""
        return "whitespace"

    def apply(self, ctx: SmeltContext) -> SmeltContext:
        """Collapse redundant whitespace outside fenced code blocks."""
        if ctx.format in _STRUCTURED_FORMATS:
            return ctx

        text = ctx.text

        # Replace fenced code blocks with placeholders, collapse, then restore
        blocks: list[str] = []

        def _save_block(m: re.Match[str]) -> str:
            idx = len(blocks)
            blocks.append(m.group(0))
            return f"\x00CODEBLOCK{idx}\x00"

        stripped = _FENCED_BLOCK_RE.sub(_save_block, text)
        collapsed = _collapse(stripped)

        # Normalize newlines around placeholders so that code blocks don't
        # introduce extra blank lines: one \n before the first placeholder,
        # no separator between adjacent placeholders, one \n after the last.
        collapsed = re.sub(r"\n{2,}(\x00CODEBLOCK)", r"\n\1", collapsed)
        collapsed = re.sub(r"(CODEBLOCK\d+\x00)\n+(\x00CODEBLOCK)", r"\1\2", collapsed)
        collapsed = re.sub(r"(CODEBLOCK\d+\x00)\n{2,}", r"\1\n", collapsed)

        # Restore code blocks
        result = collapsed
        for idx, block in enumerate(blocks):
            result = result.replace(f"\x00CODEBLOCK{idx}\x00", block)

        if result == text:
            return ctx
        return SmeltContext(text=result, format=ctx.format)


def _collapse(text: str) -> str:
    """Collapse blank lines and strip trailing whitespace in a text segment."""
    text = _TRAILING_WS_RE.sub("", text)
    text = _MULTI_BLANK_RE.sub("\n\n", text)
    # If only whitespace remains, reduce to single newline
    if not text.strip():
        return "\n" if text else text
    return text
