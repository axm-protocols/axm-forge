"""Strip-quotes strategy — remove quotes on simple JSON keys."""

from __future__ import annotations

import re

from axm_smelt.core.models import SmeltContext
from axm_smelt.strategies.base import SmeltStrategy

__all__ = ["StripQuotesStrategy"]

_SIMPLE_KEY_RE = re.compile(r'"([a-zA-Z_][\w.]*)"(?=\s*:)', re.ASCII)


class StripQuotesStrategy(SmeltStrategy):
    """Remove quotes on simple alphanumeric JSON keys."""

    @property
    def name(self) -> str:
        return "strip_quotes"

    @property
    def category(self) -> str:
        return "cosmetic"

    def apply(self, ctx: SmeltContext) -> SmeltContext:
        """Strip quotes from simple alphanumeric JSON keys.

        Operates on ``ctx.text`` via regex — no parsing required.
        """
        text = ctx.text
        result = _SIMPLE_KEY_RE.sub(r"\1", text)
        if result != text:
            return SmeltContext(text=result, format=ctx.format)
        return ctx
