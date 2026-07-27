"""Short human rendering of millisecond durations.

Canonical stdlib-only formatter so a duration like ``1500`` renders uniformly
as ``'1.5s'`` across AXM surfaces, instead of drifting between ``'1500ms'``
and ``datetime.timedelta``'s ``'0:00:01.500000'``.
"""

from __future__ import annotations

import math

__all__ = ["format_duration"]

_FALLBACK = "n/a"
_SECOND = 1_000
_MINUTE = 60_000
_HOUR = 3_600_000


def format_duration(millis: float) -> str:
    """Render a millisecond duration as a short human string.

    ``450`` → ``'450ms'``, ``1500`` → ``'1.5s'``, ``90000`` → ``'1.5min'``,
    ``5400000`` → ``'1.5h'``. Bands round to at most one decimal (rounded,
    not truncated). Negative, non-numeric or non-finite input returns
    ``'n/a'`` without raising.
    """
    try:
        value = float(millis)
    except (TypeError, ValueError):
        return _FALLBACK
    if not math.isfinite(value) or value < 0:
        return _FALLBACK
    if value < _SECOND:
        return f"{int(value)}ms"
    if value < _MINUTE:
        return f"{round(value / _SECOND, 1)}s"
    if value < _HOUR:
        return f"{round(value / _MINUTE, 1)}min"
    return f"{round(value / _HOUR, 1)}h"
