"""Unit tests for axm_audit.core.rules.test_quality.duplicate_tests."""

from __future__ import annotations

import ast
from typing import Any

from axm_audit.core.rules.base import get_registry
from axm_audit.core.rules.test_quality.duplicate_tests import (
    DuplicateTestsRule,
    _collect_assert_call_sigs,
    merge_clusters,
)


def _func(src: str) -> ast.FunctionDef:
    """Parse a function source and return the first FunctionDef."""
    tree = ast.parse(src)
    node = tree.body[0]
    assert isinstance(node, ast.FunctionDef)
    return node


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


def test_collect_assert_call_sigs_extracts_direct_call() -> None:
    node = _func("def t():\n    assert helper(1, 2) == 3\n")
    sigs = _collect_assert_call_sigs(node)
    assert any(s.startswith("helper(") for s in sigs)


def test_collect_assert_call_sigs_empty_when_no_calls() -> None:
    node = _func("def t():\n    x = 1\n    assert x == 1\n")
    assert _collect_assert_call_sigs(node) == set()


def test_collect_assert_call_sigs_multiple_distinct_sigs() -> None:
    node = _func("def t():\n    assert foo(1) == 1\n    assert bar(2, 3) == 5\n")
    sigs = _collect_assert_call_sigs(node)
    assert any(s.startswith("foo(") for s in sigs)
    assert any(s.startswith("bar(") for s in sigs)


def test_collect_assert_call_sigs_skips_non_assert_calls() -> None:
    node = _func("def t():\n    log('setup')\n    assert helper(1) == 1\n")
    sigs = _collect_assert_call_sigs(node)
    assert not any(s.startswith("log(") for s in sigs)
    assert any(s.startswith("helper(") for s in sigs)
