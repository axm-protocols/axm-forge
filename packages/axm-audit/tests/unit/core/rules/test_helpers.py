"""Unit-scope tests for _helpers module — ASTCache module-level accessors."""

from __future__ import annotations

import threading


class TestUnitScope:
    """Unit-scope tests for module-level set/get_ast_cache (no real I/O)."""

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

    def test_ast_cache_shared_across_threads(self) -> None:
        """get_ast_cache() returns the same instance in worker threads (AC1).

        Worker threads must use copy_context().run to inherit the ContextVar
        value from the parent context.
        """
        import contextvars

        from axm_audit.core.rules._helpers import (
            ASTCache,
            get_ast_cache,
            reset_ast_cache,
            set_ast_cache,
        )

        cache = ASTCache()
        token = set_ast_cache(cache)
        try:
            results: list[ASTCache | None] = []

            def worker() -> None:
                results.append(get_ast_cache())

            threads = [
                threading.Thread(target=contextvars.copy_context().run, args=(worker,))
                for _ in range(2)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(results) == 2
            assert all(r is cache for r in results)
        finally:
            reset_ast_cache(token)
