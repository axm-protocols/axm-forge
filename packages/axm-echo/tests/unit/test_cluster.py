"""Unit tests for axm_echo.cluster (pure logic, no I/O).

Mirrors ``src/axm_echo/cluster.py`` 1:1. The anti-signal predicates and the
connected-component clustering are pure functions over dicts/arrays, so they
live at the unit tier with no real boundary.
"""

from __future__ import annotations

import numpy as np

from axm_echo.cluster import (
    MIN_DOC_CHARS,
    cluster_pairs,
    cross_pairs,
    generic_docs,
    is_parallel_api,
    is_trivial_accessor,
    split_pairs,
)


def _sym(**over: object) -> dict[str, object]:
    """Build a corpus-shaped symbol dict with sensible defaults."""
    base: dict[str, object] = {
        "qualname": "pkg.mod.fn",
        "name": "fn",
        "package": "axm-thing",
        "doc_first_line": "Do a genuinely specific and unique thing here.",
        "doc_full": "Do a genuinely specific and unique thing here.",
        "embed_text": "def fn() -> None",
        "line": 1,
        "path": "/x.py",
    }
    base.update(over)
    return base


def test_is_trivial_accessor_on_return_promise() -> None:
    """A ``Return the X.`` docstring marks a trivial accessor."""
    assert is_trivial_accessor(_sym(name="name", doc_first_line="Return the name."))


def test_is_trivial_accessor_on_get_promise() -> None:
    """A ``Get the value`` docstring marks a trivial accessor."""
    assert is_trivial_accessor(_sym(name="value", doc_first_line="Get the value"))


def test_is_trivial_accessor_false_on_substantive_doc() -> None:
    """A substantive promise is not a trivial accessor."""
    sym = _sym(
        name="request_with_retry",
        doc_first_line="Perform an HTTP request, retrying with backoff on errors.",
    )
    assert not is_trivial_accessor(sym)


def test_is_parallel_api_on_package_token_prefix() -> None:
    """A pair named after its own package token is parallel API (AS2a)."""
    a = _sym(package="axm-excel", name="excel_export")
    b = _sym(package="axm-word", name="word_export")
    assert is_parallel_api(a, b)


def test_is_parallel_api_false_for_same_named_cross_package() -> None:
    """A genuine same-named cross-package symbol is not parallel API."""
    a = _sym(package="axm-commons", name="RateLimitError")
    b = _sym(package="axm-bib", name="RateLimitError")
    assert not is_parallel_api(a, b)


def test_generic_docs_flags_recurring_first_lines() -> None:
    """A first-line shared across >= min_repeat symbols is boilerplate."""
    syms = [_sym(doc_first_line="CLI entry point.") for _ in range(4)]
    syms.append(_sym(doc_first_line="A unique and specific promise here."))
    generic = generic_docs(syms, min_repeat=4)
    assert "cli entry point." in generic
    assert "a unique and specific promise here." not in generic


def test_generic_docs_keeps_unique_terse_line() -> None:
    """A unique terse first-line is NOT boilerplate (POC lesson)."""
    syms = [_sym(doc_first_line="502/503/504 - service temporarily down.")]
    syms += [_sym(doc_first_line="CLI entry point.") for _ in range(4)]
    assert "502/503/504 - service temporarily down." not in generic_docs(syms)


def test_cross_pairs_keeps_only_cross_package_above_threshold() -> None:
    """cross_pairs returns distinct-package upper-triangle pairs over threshold."""
    # Rows 0 and 1 identical (sim 1.0), row 2 orthogonal.
    matrix = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]], dtype=np.float64)
    packages = ["axm-a", "axm-b", "axm-a"]
    pairs = cross_pairs(matrix, packages, threshold=0.55)
    assert pairs == [(0, 1, 1.0)]


def test_cross_pairs_drops_same_package_pairs() -> None:
    """Two identical symbols in the same package are not a cross-package pair."""
    matrix = np.array([[1.0, 0.0], [1.0, 0.0]], dtype=np.float64)
    pairs = cross_pairs(matrix, ["axm-a", "axm-a"], threshold=0.55)
    assert pairs == []


def test_split_pairs_routes_each_bucket() -> None:
    """split_pairs sends boilerplate, parallel, and dupes to their buckets."""
    symbols = [
        _sym(package="axm-excel", name="excel_export"),  # 0 parallel
        _sym(package="axm-word", name="word_export"),  # 1 parallel
        _sym(
            package="axm-a",
            name="x",
            doc_first_line="CLI entry point.",
            doc_full="CLI entry point.",
        ),  # 2 boilerplate
        _sym(
            package="axm-b",
            name="y",
            doc_first_line="CLI entry point.",
            doc_full="CLI entry point.",
        ),  # 3 boilerplate
        _sym(package="axm-commons", name="RateLimitError"),  # 4 dupe
        _sym(package="axm-bib", name="RateLimitError"),  # 5 dupe
    ]
    generic = {"cli entry point."}
    pairs = [(0, 1, 0.9), (2, 3, 0.99), (4, 5, 0.97)]
    dupes, parallel, boilerplate = split_pairs(pairs, symbols, generic)
    assert dupes == [(4, 5, 0.97)]
    assert parallel == [(0, 1, 0.9)]
    assert boilerplate == [(2, 3, 0.99)]


def test_cluster_pairs_merges_transitive_into_one_component() -> None:
    """Transitively-linked pairs collapse into a single cluster."""
    clusters = cluster_pairs([(0, 1, 0.9), (1, 2, 0.8), (5, 6, 0.7)])
    assert [set(c) for c in clusters] == [{0, 1, 2}, {5, 6}]


def test_cluster_pairs_empty_returns_no_clusters() -> None:
    """No pairs means no clusters."""
    assert cluster_pairs([]) == []


def test_min_doc_chars_is_a_positive_floor() -> None:
    """The terse-doc floor is a small positive constant."""
    assert 0 < MIN_DOC_CHARS < 30


def _chain(node_ids: list[int]) -> list[tuple[int, int, float]]:
    """Link node_ids into one connected component via a chain of pairs."""
    return [(node_ids[k], node_ids[k + 1], 0.9) for k in range(len(node_ids) - 1)]


def test_mega_cluster_rejected() -> None:
    """AC1: a cluster beyond max_cluster_size is dropped; a small one is kept."""
    mega = list(range(0, 60))
    small = [200, 201, 202]
    pairs = _chain(mega) + _chain(small)

    clusters = cluster_pairs(pairs, max_cluster_size=50)

    sizes = {len(c) for c in clusters}
    assert 60 not in sizes
    assert any(len(c) == 3 for c in clusters)
    assert all(len(c) <= 50 for c in clusters)
