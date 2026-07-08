"""Unit tests for the demoted-pair serialization bound (MCP payload safety).

``_pair_entries`` bounds the parallel-API / boilerplate buckets so a large
corpus cannot blow the MCP transport chunk budget. Pure list logic, no I/O.
"""

from __future__ import annotations

from axm_echo.tools import _MAX_DEMOTED_PAIRS, _pair_entries


def _sym(i: int) -> dict[str, object]:
    """A minimal corpus-shaped symbol for member serialization."""
    return {
        "qualname": f"pkg.mod.fn{i}",
        "name": f"fn{i}",
        "package": f"axm-p{i}",
        "doc_first_line": "boilerplate promise.",
        "path": f"/x{i}.py",
        "line": i,
    }


def test_pair_entries_bounds_the_bucket() -> None:
    """More pairs than the bound serialize to at most the bound, strongest first."""
    n = _MAX_DEMOTED_PAIRS + 25
    symbols = [_sym(i) for i in range(n + 1)]
    # score increases with i, so the top slice must be the highest-i pairs.
    pairs = [(i, i + 1, 0.5 + i / (10 * n)) for i in range(n)]

    entries = _pair_entries(pairs, symbols)

    assert len(entries) == _MAX_DEMOTED_PAIRS
    scores = [e["score"] for e in entries]
    assert scores == sorted(scores, reverse=True)
    # The strongest pair (largest i) survived the bound.
    assert entries[0]["a"]["name"] == f"fn{n - 1}"


def test_pair_entries_below_bound_keeps_all() -> None:
    """A bucket smaller than the bound is serialized whole."""
    symbols = [_sym(i) for i in range(4)]
    pairs = [(0, 1, 0.9), (2, 3, 0.8)]

    entries = _pair_entries(pairs, symbols)

    assert len(entries) == 2
