"""Compact markdown table whitespace."""

from __future__ import annotations

import re

from axm_smelt.core.models import Format, SmeltContext
from axm_smelt.strategies.base import SmeltStrategy

__all__ = ["CompactTablesStrategy"]

_TABLE_LINE_RE = re.compile(r"^\|.*\|$")


def _compact_table_line(line: str) -> str:
    """Strip whitespace from each cell in a table line."""
    parts = line.split("|")
    # parts[0] is '' (before leading |), parts[-1] is '' (after trailing |)
    cells = [p.strip() for p in parts[1:-1]]
    result = "|" + "|".join(cells) + "|"
    # Collapse runs of empty cells: ||| → ||
    return re.sub(r"\|{3,}", "||", result)


class CompactTablesStrategy(SmeltStrategy):
    """Remove padding whitespace from markdown table cells."""

    @property
    def name(self) -> str:
        """Strategy identifier used in the registry."""
        return "compact_tables"

    @property
    def category(self) -> str:
        """Strategy category (``whitespace``)."""
        return "whitespace"

    def apply(self, ctx: SmeltContext) -> SmeltContext:
        if ctx.format is not Format.MARKDOWN:
            return ctx

        lines = ctx.text.split("\n")
        out: list[str] = []
        changed = False
        in_fenced = False

        for line in lines:
            if line.startswith("```"):
                in_fenced = not in_fenced
                out.append(line)
                continue

            if in_fenced or not _TABLE_LINE_RE.match(line):
                out.append(line)
                continue

            compacted = _compact_table_line(line)

            if compacted != line:
                changed = True
            out.append(compacted)

        if not changed:
            return ctx

        return SmeltContext(text="\n".join(out), format=ctx.format)
