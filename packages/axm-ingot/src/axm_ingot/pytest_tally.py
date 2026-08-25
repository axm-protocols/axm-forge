"""Tally pytest outcome lines (FAILED/ERROR/SKIPPED/...) into per-kind counts.

Stdlib-only helper: classify each line by its leading whitespace-stripped,
lower-cased first token. Unrecognised or malformed elements are routed to the
``unknown`` bucket so the sum of all buckets always equals the input length.
"""

from __future__ import annotations

from collections.abc import Iterable

__all__ = ["tally_outcomes"]

_KINDS = ("failed", "error", "skipped")


def tally_outcomes(lines: Iterable[object]) -> dict[str, int]:
    """Count pytest outcome lines per kind.

    Args:
        lines: An iterable of outcome lines (typically pytest short-summary
            lines such as ``"FAILED tests/..."``). Non-string / ``None`` /
            malformed elements are tolerated.

    Returns:
        A dict with the fixed keys ``failed``/``error``/``skipped``/``unknown``
        (each always present, initialised to ``0``). Every input element
        increments exactly one bucket, so the bucket sum equals the number of
        elements.
    """
    tally: dict[str, int] = {"failed": 0, "error": 0, "skipped": 0, "unknown": 0}
    for line in lines:
        tally[_classify(line)] += 1
    return tally


def _classify(line: object) -> str:
    """Return the bucket key for a single outcome line."""
    if not isinstance(line, str):
        return "unknown"
    tokens = line.strip().split()
    if not tokens:
        return "unknown"
    keyword = tokens[0].lower()
    return keyword if keyword in _KINDS else "unknown"
