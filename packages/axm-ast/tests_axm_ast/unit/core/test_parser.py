"""Unit tests for axm_ast.core.parser — parse_source, parse_file.

All tests are pure / no real I/O (parse_source operates on in-memory
strings; parse_file only touches small static fixtures).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from tree_sitter import Tree

from axm_ast.core.parser import (
    ParseCacheStats,
    clear_parse_cache,
    parse_cache_stats,
    parse_file,
    parse_source,
)

FIXTURES = Path(__file__).resolve().parent.parent.parent / "fixtures"
SAMPLE_PKG = FIXTURES / "sample_pkg"


# ────────────────────────────────────────────────────────────────────────────
# parse_source
# ────────────────────────────────────────────────────────────────────────────


class TestParseSource:
    """Tests for parse_source()."""

    def test_syntax_error_graceful(self) -> None:
        """Tree-sitter should parse even with syntax errors."""
        tree = parse_source("def broken(")
        assert tree.root_node.has_error is True

    def test_parse_source_returns_tree(self) -> None:
        """AC3: parse_source returns a Tree with the expected root node type."""
        tree = parse_source("def foo(): pass")
        assert tree.root_node.type == "module"
        assert tree.root_node.has_error is False

    def test_parse_source_concurrent_threads_consistent(self) -> None:
        """AC2: concurrent parses of distinct sources match single-threaded parse.

        Parses N varied snippets across a thread pool and asserts every
        thread's tree (root type + node count) equals the single-threaded
        parse of the same snippet — i.e. no shared, corrupted parser state.
        """
        snippets = [
            f"def f{i}(a, b):\n    return a + b + {i}\n\nclass C{i}:\n    x = {i}\n"
            for i in range(64)
        ]

        def fingerprint(tree: Tree) -> tuple[str, int, bool]:
            root = tree.root_node
            return (root.type, root.descendant_count, root.has_error)

        expected = [fingerprint(parse_source(s)) for s in snippets]

        with ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(parse_source, snippets * 4))

        actual = [fingerprint(tree) for tree in results]
        assert actual == (expected * 4)


# ────────────────────────────────────────────────────────────────────────────
# parse_file
# ────────────────────────────────────────────────────────────────────────────


class TestParseFileUnit:
    """Tests for parse_file() — pure, no real I/O."""

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            parse_file(Path("/nonexistent/path.py"))

    def test_broken_file(self) -> None:
        """Broken syntax should still parse (graceful degradation)."""
        tree = parse_file(FIXTURES / "broken.py")
        assert tree.root_node.has_error is True


# ────────────────────────────────────────────────────────────────────────────
# parse_cache_stats
# ────────────────────────────────────────────────────────────────────────────


class TestParseCacheStats:
    """Tests for parse_cache_stats()."""

    def test_cleared_cache_is_empty(self) -> None:
        """After a reset the LRU holds no tree and reports its capacity."""
        clear_parse_cache()
        stats = parse_cache_stats()
        assert stats.entries == 0
        assert stats.max_entries > 0

    def test_parse_file_occupies_one_slot(self) -> None:
        """Parsing a file stores exactly one tree; re-parsing reuses it."""
        clear_parse_cache()
        target = SAMPLE_PKG / "__init__.py"
        parse_file(target)
        parse_file(target)
        assert parse_cache_stats() == ParseCacheStats(
            entries=1, max_entries=parse_cache_stats().max_entries
        )
