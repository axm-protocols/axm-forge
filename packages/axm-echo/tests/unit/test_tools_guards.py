"""Unit tests for the ``echo_code`` / ``echo_check`` guards + payload bound.

These exercise the pre-flight validation branches that short-circuit *before*
any corpus access, plus the demoted-pair serialization bound -- all pure logic,
no filesystem. ``tools.py`` is mirror-exempt, hence the dedicated guard file.
"""

from __future__ import annotations

import pytest

from axm_echo.tools import (
    MAX_DEMOTED_PAIRS,
    EchoCheckTool,
    EchoCodeTool,
    pair_entries,
)


@pytest.mark.parametrize(
    ("kwargs", "needle"),
    [
        ({"backend": "bogus"}, "invalid backend"),
        ({"threshold": 1.5}, "cosine in [0.0, 1.0]"),
        ({"threshold": -0.1}, "cosine in [0.0, 1.0]"),
        ({"top_n": 0}, "top_n must be >= 1"),
        ({"max_cluster_size": 0}, "max_cluster_size must be >= 1"),
    ],
)
def test_echo_code_invalid_input_returns_error_result(
    kwargs: dict[str, object], needle: str
) -> None:
    result = EchoCodeTool().execute(**kwargs)
    assert result.success is False
    assert needle in (result.error or "").lower()


@pytest.mark.parametrize(
    ("kwargs", "needle"),
    [
        ({"intention": "x", "backend": "bogus"}, "invalid backend"),
        ({"intention": "x", "k": 0}, "k must be >= 1"),
        ({"intention": "x", "k": -2}, "k must be >= 1"),
        ({"intention": "x", "threshold": 1.5}, "cosine in [0.0, 1.0]"),
        ({"intention": "x", "threshold": -0.1}, "cosine in [0.0, 1.0]"),
        ({"intention": "   "}, "intention must be a non-empty string"),
    ],
)
def test_echo_check_invalid_input_returns_error_result(
    kwargs: dict[str, object], needle: str
) -> None:
    result = EchoCheckTool().execute(**kwargs)
    assert result.success is False
    assert needle in (result.error or "").lower()


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
    n = MAX_DEMOTED_PAIRS + 25
    symbols = [_sym(i) for i in range(n + 1)]
    # score increases with i, so the top slice must be the highest-i pairs.
    pairs = [(i, i + 1, 0.5 + i / (10 * n)) for i in range(n)]

    entries = pair_entries(pairs, symbols)

    assert len(entries) == MAX_DEMOTED_PAIRS
    scores = [e["score"] for e in entries]
    assert scores == sorted(scores, reverse=True)
    # The strongest pair (largest i) survived the bound.
    assert entries[0]["a"]["name"] == f"fn{n - 1}"


def test_pair_entries_below_bound_keeps_all() -> None:
    """A bucket smaller than the bound is serialized whole."""
    symbols = [_sym(i) for i in range(4)]
    pairs = [(0, 1, 0.9), (2, 3, 0.8)]

    entries = pair_entries(pairs, symbols)

    assert len(entries) == 2
