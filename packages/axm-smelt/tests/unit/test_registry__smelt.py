"""Round-trip reversibility safety net for the lossless strategies.

AC4: each strictly-lossless strategy must satisfy
``json.loads(out) == json.loads(in)`` on structured JSON input.
AC3: the ``safe`` preset is NOT byte/whitespace-lossless on prose.

These tests are the regression net that would have caught the README
drift fixed in AXM-1998 (e.g. a value-mutating strategy mislabeled
lossless, or ``safe`` advertised as whitespace-lossless on prose).

Non-mirrorable scenario at unit level: a pure-memory public-API check
spanning the strategy REGISTRY (in the mirror-exempt ``strategies/
__init__.py``) and the ``smelt`` pipeline across several strategies.
No single source module mirrors it, so it is mirror-exempt (see
``[tool.axm-audit.mirror].exempt_paths`` in ``pyproject.toml``).
"""

from __future__ import annotations

import json

import pytest

from axm_smelt import smelt
from axm_smelt.strategies import REGISTRY

# Strictly-lossless strategies on structured JSON: they either reformat
# whitespace only (``minify``) or are no-ops on structured formats
# (``collapse_whitespace``, ``strip_html_comments``, ``compact_tables``).
# Every other registry strategy intentionally mutates values or shape
# (drop_nulls, flatten, tabular, round_numbers, strip_quotes,
# dedup_values_with_refs) and is excluded by design.
LOSSLESS_STRATEGIES = [
    "minify",
    "collapse_whitespace",
    "strip_html_comments",
    "compact_tables",
]

# Structured input with nesting, a null, a float and an array so that a
# value- or shape-mutating strategy slipping into the lossless set would
# break the round-trip assertion.
_STRUCTURED_INPUT = json.dumps(
    {
        "name": "alpha",
        "count": 42,
        "ratio": 3.14159,
        "note": None,
        "tags": ["x", "y", "z"],
        "nested": {"a": 1, "b": [True, False]},
    },
    indent=2,
)


def test_lossless_strategies_are_registered() -> None:
    """AC4: the lossless set is a subset of the real REGISTRY."""
    assert set(LOSSLESS_STRATEGIES) <= set(REGISTRY)


@pytest.mark.parametrize("strategy", LOSSLESS_STRATEGIES)
def test_lossless_strategy_roundtrip(strategy: str) -> None:
    """AC4: lossless strategy preserves structured data round-trip."""
    report = smelt(text=_STRUCTURED_INPUT, strategies=[strategy])

    assert json.loads(report.compacted) == json.loads(_STRUCTURED_INPUT)


def test_safe_preset_not_whitespace_lossless_on_prose() -> None:
    """AC3: ``safe`` collapses prose whitespace -> not byte-lossless."""
    prose = (
        "# Title\n"
        "\n"
        "\n"
        "\n"
        "First paragraph with trailing spaces.   \n"
        "\n"
        "\n"
        "Second paragraph.\n"
    )

    report = smelt(text=prose, preset="safe")

    # collapse_whitespace mutates blank-line runs / trailing whitespace,
    # so ``safe`` is documented as NOT byte/whitespace-lossless on prose.
    assert report.compacted != prose
