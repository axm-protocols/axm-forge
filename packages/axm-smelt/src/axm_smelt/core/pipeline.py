"""Smelt pipeline — detect, count, compact."""

from __future__ import annotations

import json

from axm_smelt._types import JsonValue
from axm_smelt.core.counter import (  # noqa: F401
    CounterBackend,
    count,
    count_with_backend,
)
from axm_smelt.core.detector import detect_format, detect_format_parsed
from axm_smelt.core.models import SmeltContext, SmeltReport
from axm_smelt.strategies import get_preset, get_strategy
from axm_smelt.strategies.base import SmeltStrategy

__all__ = ["check", "smelt"]


def _worst(a: CounterBackend, b: CounterBackend) -> CounterBackend:
    """Return ``FALLBACK`` if either input is ``FALLBACK``, else ``TIKTOKEN``."""
    if a is CounterBackend.FALLBACK or b is CounterBackend.FALLBACK:
        return CounterBackend.FALLBACK
    return CounterBackend.TIKTOKEN


def _resolve_input(
    text: str | None,
    parsed: dict[str, JsonValue] | list[JsonValue] | None,
) -> tuple[str, dict[str, JsonValue] | list[JsonValue] | None]:
    """Normalize inputs into ``(text, parsed)``."""
    if parsed is not None:
        return json.dumps(parsed, separators=(",", ":")), parsed
    if text is None:
        msg = "Either text or parsed must be provided"
        raise ValueError(msg)
    return text, None


def _resolve_strategies(
    strategies: list[str] | None,
    preset: str | None,
) -> list[SmeltStrategy]:
    """Return strategy instances from explicit names, a preset, or the default."""
    if strategies:
        return [get_strategy(s) for s in strategies]
    if preset:
        return get_preset(preset)
    return get_preset("safe")


def _apply_strategies(
    ctx: SmeltContext,
    strats: list[SmeltStrategy],
    current_tokens: int,
) -> tuple[SmeltContext, list[str], CounterBackend]:
    """Apply *strats* to *ctx*, discarding any that increase tokens."""
    applied: list[str] = []
    backend = CounterBackend.TIKTOKEN
    for s in strats:
        result = s.apply(ctx)
        if result.text != ctx.text:
            result_tokens, b = count_with_backend(result.text)
            backend = _worst(backend, b)
            if result_tokens < current_tokens or (
                result_tokens == current_tokens and len(result.text) < len(ctx.text)
            ):
                applied.append(s.name)
                ctx = result
                current_tokens = result_tokens
    return ctx, applied, backend


def smelt(
    text: str | None = None,
    strategies: list[str] | None = None,
    preset: str | None = None,
    *,
    parsed: dict[str, JsonValue] | list[JsonValue] | None = None,
) -> SmeltReport:
    """Run the compaction pipeline and return a report."""
    text, parsed = _resolve_input(text, parsed)

    fmt, detected_parsed = detect_format_parsed(text)
    if parsed is not None:
        detected_parsed = parsed
    original_tokens, b1 = count_with_backend(text)

    strats = _resolve_strategies(strategies, preset)

    if detected_parsed is not None:
        ctx = SmeltContext(text=text, format=fmt, parsed=detected_parsed)
    else:
        ctx = SmeltContext(text=text, format=fmt)

    ctx, applied, b_strat = _apply_strategies(ctx, strats, original_tokens)

    compacted = ctx.text
    compacted_tokens, b3 = count_with_backend(compacted)
    backend = _worst(_worst(b1, b_strat), b3)
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
        counter_backend=backend,
    )


def check(
    text: str | None = None,
    *,
    parsed: dict[str, JsonValue] | list[JsonValue] | None = None,
) -> SmeltReport:
    """Analyze *text* without transforming it."""
    from axm_smelt.strategies import _REGISTRY

    if parsed is not None:
        text = json.dumps(parsed, separators=(",", ":"))
    elif text is None:
        msg = "Either text or parsed must be provided"
        raise ValueError(msg)

    fmt = detect_format(text)
    tokens, backend = count_with_backend(text)

    ctx = SmeltContext(text=text, format=fmt)
    estimates: dict[str, float] = {}
    for name, cls in _REGISTRY.items():
        strategy = cls()
        result = strategy.apply(ctx)
        if result.text != ctx.text:
            result_tokens, b = count_with_backend(result.text)
            backend = _worst(backend, b)
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
        counter_backend=backend,
    )
