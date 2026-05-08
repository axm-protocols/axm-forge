"""Unit tests for axm_audit.core.rules.test_quality.duplicate_tests."""

from __future__ import annotations

from typing import Any

from axm_audit.core.rules.base import get_registry
from axm_audit.core.rules.test_quality.duplicate_tests import (
    DuplicateTestsRule,
    merge_clusters,
)


def _make_cluster(signal: str, tests: list[tuple[str, str]]) -> dict[str, Any]:
    return {
        "signal": signal,
        "similarity": 0.9,
        "tests": [{"file": f, "name": n} for f, n in tests],
    }


def test_rule_registered() -> None:
    registry = get_registry()
    bucket = registry.get("test_quality", [])
    assert DuplicateTestsRule in bucket


def test_merge_ambiguous_dominates() -> None:
    sub_clusters = [
        _make_cluster(
            "signal1_call_assert",
            [("tests/test_mod.py", "test_a"), ("tests/test_mod.py", "test_b")],
        ),
        _make_cluster(
            "ambiguous_distinct_literals",
            [("tests/test_mod.py", "test_a"), ("tests/test_mod.py", "test_c")],
        ),
    ]
    merged = merge_clusters(sub_clusters)
    assert len(merged) == 1
    assert merged[0]["signal"] == "ambiguous_distinct_literals"


def test_merge_multi_signal() -> None:
    sub_clusters = [
        _make_cluster(
            "signal1_call_assert",
            [("tests/test_mod.py", "test_a"), ("tests/test_mod.py", "test_b")],
        ),
        _make_cluster(
            "signal3_intra_file_similarity",
            [("tests/test_mod.py", "test_a"), ("tests/test_mod.py", "test_c")],
        ),
    ]
    merged = merge_clusters(sub_clusters)
    assert len(merged) == 1
    assert merged[0]["signal"] == "multi_signal"


def test_merge_ambiguous_multi() -> None:
    sub_clusters = [
        _make_cluster(
            "ambiguous_distinct_literals",
            [("tests/test_mod.py", "test_a"), ("tests/test_mod.py", "test_b")],
        ),
        _make_cluster(
            "ambiguous_patch_context",
            [("tests/test_mod.py", "test_a"), ("tests/test_mod.py", "test_c")],
        ),
    ]
    merged = merge_clusters(sub_clusters)
    assert len(merged) == 1
    assert merged[0]["signal"] == "ambiguous_multi"
