from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from axm_audit.core.rules._helpers import ASTCache, get_active_cache, set_ast_cache


def test_set_ast_cache_returns_token_and_resets() -> None:
    """AC3: set_ast_cache returns a Token; reset restores None."""
    cache = ASTCache()
    token = set_ast_cache(cache)

    assert get_active_cache() is cache

    # Token-based reset must restore the previous value (None)
    from axm_audit.core.rules._helpers import reset_ast_cache

    reset_ast_cache(token)
    assert get_active_cache() is None


def test_active_cache_isolated_between_threads() -> None:
    """AC1, AC2: Each thread sees its own ASTCache; main is unaffected."""
    results: dict[str, ASTCache | None] = {}
    barrier = threading.Barrier(2)

    def worker(name: str) -> None:
        cache = ASTCache()
        token = set_ast_cache(cache)
        results[f"{name}_set"] = get_active_cache()
        barrier.wait()  # ensure both threads overlap
        time.sleep(0.05)
        results[f"{name}_read"] = get_active_cache()
        from axm_audit.core.rules._helpers import reset_ast_cache

        reset_ast_cache(token)
        results[f"{name}_after"] = get_active_cache()

    # Main thread should have no cache
    assert get_active_cache() is None

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(worker, "t1")
        f2 = pool.submit(worker, "t2")
        f1.result()
        f2.result()

    # Each thread set its own cache and read it back
    assert isinstance(results["t1_set"], ASTCache)
    assert isinstance(results["t2_set"], ASTCache)
    assert results["t1_set"] is not results["t2_set"]

    # Each thread still saw its own cache after overlap
    assert results["t1_read"] is results["t1_set"]
    assert results["t2_read"] is results["t2_set"]

    # After reset, each thread saw None
    assert results["t1_after"] is None
    assert results["t2_after"] is None

    # Main thread unaffected
    assert get_active_cache() is None


def test_active_cache_propagates_to_threadpool_worker() -> None:
    """AC1: Worker threads inside audit_project see the caller's ASTCache."""
    observed_caches: list[ASTCache | None] = []

    from axm_audit.core import auditor as auditor_mod
    from axm_audit.core.auditor import CheckResult

    def _capturing_safe_check(rule, project_path):
        observed_caches.append(get_active_cache())
        return CheckResult(rule_id="fake", category="test", passed=True, message="")

    with patch.object(auditor_mod, "_safe_check", side_effect=_capturing_safe_check):
        with patch.object(
            auditor_mod,
            "get_rules_for_category",
            return_value=[type("FakeRule", (), {"check": lambda self, p: None})()],
        ):
            import tempfile
            from pathlib import Path

            with tempfile.TemporaryDirectory() as tmp:
                auditor_mod.audit_project(Path(tmp))

    # The worker must have seen a non-None ASTCache
    assert len(observed_caches) >= 1
    assert all(isinstance(c, ASTCache) for c in observed_caches)
