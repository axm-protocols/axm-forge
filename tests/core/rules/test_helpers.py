"""Tests for _helpers module — ASTCache and utility functions."""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import patch


class TestASTCache:
    """Tests for ASTCache class."""

    def test_returns_same_object(self, tmp_path: Path) -> None:
        """Two calls with the same path return the same AST object."""
        from axm_audit.core.rules._helpers import ASTCache

        f = tmp_path / "example.py"
        f.write_text("x = 1\n")

        cache = ASTCache()
        tree1 = cache.get_or_parse(f)
        tree2 = cache.get_or_parse(f)
        assert tree1 is tree2
        assert tree1 is not None

    def test_syntax_error_returns_none(self, tmp_path: Path) -> None:
        """Files with syntax errors are cached as None without retry."""
        from axm_audit.core.rules._helpers import ASTCache

        f = tmp_path / "broken.py"
        f.write_text("def foo(\n")  # syntax error

        cache = ASTCache()
        result = cache.get_or_parse(f)
        assert result is None

        # Second call should return cached None (not re-parse)
        with patch("axm_audit.core.rules._helpers.parse_file_safe") as mock:
            mock.return_value = None
            result2 = cache.get_or_parse(f)
            assert result2 is None
            mock.assert_not_called()

    def test_thread_safe(self, tmp_path: Path) -> None:
        """Multiple threads parsing the same file → only 1 actual parse."""
        from axm_audit.core.rules._helpers import ASTCache

        f = tmp_path / "shared.py"
        f.write_text("y = 42\n")

        cache = ASTCache()
        results: list[object] = []
        barrier = threading.Barrier(10)

        def worker() -> None:
            barrier.wait()
            results.append(cache.get_or_parse(f))

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All results should be the same object
        assert len(results) == 10
        assert all(r is results[0] for r in results)


class TestASTCacheAccessors:
    """Tests for thread-local set/get_ast_cache."""

    def test_default_is_none(self) -> None:
        """get_ast_cache returns None when not set."""
        from axm_audit.core.rules._helpers import get_ast_cache

        assert get_ast_cache() is None

    def test_set_and_get(self) -> None:
        """set_ast_cache stores a cache retrievable by get_ast_cache."""
        from axm_audit.core.rules._helpers import ASTCache, get_ast_cache, set_ast_cache

        cache = ASTCache()
        set_ast_cache(cache)
        try:
            assert get_ast_cache() is cache
        finally:
            set_ast_cache(None)

    def test_clear(self) -> None:
        """Setting None clears the cache."""
        from axm_audit.core.rules._helpers import ASTCache, get_ast_cache, set_ast_cache

        set_ast_cache(ASTCache())
        set_ast_cache(None)
        assert get_ast_cache() is None
