"""Split from ``test_helpers.py``."""

import threading
from pathlib import Path


def test_ast_cache_parse_count(tmp_path: Path) -> None:
    """Same file parsed from 3 threads → exactly 1 cache entry (AC2)."""
    from axm_audit.core.rules._helpers import ASTCache, set_ast_cache

    f = tmp_path / "shared.py"
    f.write_text("x = 1\n")

    cache = ASTCache()
    set_ast_cache(cache)
    try:
        barrier = threading.Barrier(3)

        def worker() -> None:
            barrier.wait()
            cache.get_or_parse(f)

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(cache._cache) == 1
    finally:
        set_ast_cache(None)
