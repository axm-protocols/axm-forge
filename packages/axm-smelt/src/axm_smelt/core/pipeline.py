"""Smelt pipeline — detect, count, compact."""

from __future__ import annotations

import json
from typing import Any

from axm_smelt.core.counter import count
from axm_smelt.core.detector import detect_format, detect_format_parsed
from axm_smelt.core.models import SmeltContext, SmeltReport
from axm_smelt.strategies import get_preset, get_strategy
from axm_smelt.strategies.base import SmeltStrategy

__all__ = ["check", "smelt"]


def smelt(
    text: str | None = None,
    strategies: list[str] | None = None,
    preset: str | None = None,
    *,
    parsed: dict[str, Any] | list[Any] | None = None,
) -> SmeltReport:
    """Run the compaction pipeline and return a report."""
    if parsed is not None:
        text = json.dumps(parsed, separators=(",", ":"))
    elif text is None:
        msg = "Either text or parsed must be provided"
        raise ValueError(msg)

    fmt, _parsed = detect_format_parsed(text)
    if parsed is not None:
        _parsed = parsed
    original_tokens = count(text)

    strats: list[SmeltStrategy]
    if strategies:
        strats = [get_strategy(s) for s in strategies]
    elif preset:
        strats = get_preset(preset)
    else:
        strats = get_preset("safe")

    ctx = SmeltContext(text=text, format=fmt)
    if _parsed is not None:
        ctx._parsed = _parsed
    applied: list[str] = []
    current_tokens = original_tokens
    for s in strats:
        result = s.apply(ctx)
        if result.text != ctx.text:
            result_tokens = count(result.text)
            if result_tokens < current_tokens or (
                result_tokens == current_tokens and len(result.text) < len(ctx.text)
            ):
                applied.append(s.name)
                ctx = result
                current_tokens = result_tokens

    compacted = ctx.text
    compacted_tokens = count(compacted)
    savings = (
        (1 - compacted_tokens / original_tokens) * 100 if original_tokens > 0 else 0.0
    )

    return SmeltReport(
        original=text,
        compacted=compacted,
        original_tokens=original_tokens,
        compacted_tokens=compacted_tokens,
        savings_pct=savings,
        format=fmt,
        strategies_applied=applied,
    )


def check(
    text: str | None = None,
    *,
    parsed: dict[str, Any] | list[Any] | None = None,
) -> SmeltReport:
    """Analyze *text* without transforming it."""
    from axm_smelt.strategies import _REGISTRY

    if parsed is not None:
        text = json.dumps(parsed, separators=(",", ":"))
    elif text is None:
        msg = "Either text or parsed must be provided"
        raise ValueError(msg)

    fmt = detect_format(text)
    tokens = count(text)

    ctx = SmeltContext(text=text, format=fmt)
    estimates: dict[str, float] = {}
    for name, cls in _REGISTRY.items():
        strategy = cls()
        result = strategy.apply(ctx)
        if result.text != ctx.text:
            result_tokens = count(result.text)
            savings = (1 - result_tokens / tokens) * 100 if tokens > 0 else 0.0
            if savings > 0:
                estimates[name] = round(savings, 2)

    return SmeltReport(
        original=text,
        compacted=text,
        original_tokens=tokens,
        compacted_tokens=tokens,
        savings_pct=0.0,
        format=fmt,
        strategies_applied=[],
        strategy_estimates=estimates,
    )
