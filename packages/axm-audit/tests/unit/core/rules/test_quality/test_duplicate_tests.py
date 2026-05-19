"""Unit tests for axm_audit.core.rules.test_quality.duplicate_tests."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from axm_audit.core.rules.base import get_registry
from axm_audit.core.rules.test_quality.duplicate_tests import (
    _MAX_TEXT_CLUSTERS,
    DuplicateTestsRule,
    _cluster_hash,
    _slim_clusters,
    collect_assert_call_sigs,
    make_test_func,
    merge_clusters,
    p10_rescues,
    render_clusters_text,
)


def _make_tf(src: str, line: int) -> Any:
    """Parse a function source and build a _TestFunc with the given line."""
    node = _func(src)
    node.lineno = line
    return make_test_func("tests/test_mod.py", node, None)


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
        "members": [{"file": f, "name": n} for f, n in tests],
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


def testcollect_assert_call_sigs_extracts_direct_call() -> None:
    node = _func("def t():\n    assert helper(1, 2) == 3\n")
    sigs = collect_assert_call_sigs(node)
    assert any(s.startswith("helper(") for s in sigs)


def testcollect_assert_call_sigs_empty_when_no_calls() -> None:
    node = _func("def t():\n    x = 1\n    assert x == 1\n")
    assert collect_assert_call_sigs(node) == set()


def testcollect_assert_call_sigs_multiple_distinct_sigs() -> None:
    node = _func("def t():\n    assert foo(1) == 1\n    assert bar(2, 3) == 5\n")
    sigs = collect_assert_call_sigs(node)
    assert any(s.startswith("foo(") for s in sigs)
    assert any(s.startswith("bar(") for s in sigs)


def testcollect_assert_call_sigs_skips_non_assert_calls() -> None:
    node = _func("def t():\n    log('setup')\n    assert helper(1) == 1\n")
    sigs = collect_assert_call_sigs(node)
    assert not any(s.startswith("log(") for s in sigs)
    assert any(s.startswith("helper(") for s in sigs)


def testp10_rescues_skips_when_close() -> None:
    a = _make_tf("def t():\n    assert helper(1) == 1\n", line=10)
    b = _make_tf("def t():\n    assert helper(2) == 2\n", line=50)
    assert p10_rescues([a, b]) is False


def testp10_rescues_fires_when_far_apart_weak_signal() -> None:
    # Different stmt structure (1 stmt vs 2 stmts), different attrs, different
    # call_sigs — so no very-strong bypass fires. Far apart → P10 should fire.
    a = _make_tf("def t():\n    assert foo() == 1\n", line=10)
    b = _make_tf(
        "def t():\n    x = bar()\n    y = baz(x)\n    assert y > 0\n",
        line=400,
    )
    assert p10_rescues([a, b]) is True


def testp10_rescues_bypasses_on_high_stmt_jaccard() -> None:
    body = "def t():\n    assert foo(1) == 1\n"
    a = _make_tf(body, line=10)
    b = _make_tf(body, line=500)
    assert p10_rescues([a, b]) is False


def testp10_rescues_bypasses_on_shared_asserted_attrs() -> None:
    src_a = (
        "def t():\n"
        "    r = run()\n"
        "    assert r.passed\n"
        "    assert r.details\n"
        "    assert r.score\n"
    )
    src_b = (
        "def t():\n"
        "    r = exec_other()\n"
        "    assert r.passed\n"
        "    assert r.details\n"
        "    assert r.score\n"
    )
    a = _make_tf(src_a, line=10)
    b = _make_tf(src_b, line=500)
    assert p10_rescues([a, b]) is False


def testp10_rescues_bypasses_on_same_callsig_and_shared_literals() -> None:
    src_a = "def t():\n    assert helper('A', 'B', 'C') == 'OK'\n"
    src_b = "def t():\n    assert helper('A', 'B', 'C') == 'OK'\n"
    a = _make_tf(src_a, line=10)
    b = _make_tf(src_b, line=500)
    assert p10_rescues([a, b]) is False


def testp10_rescues_singleton_returns_false() -> None:
    a = _make_tf("def t():\n    assert helper(1) == 1\n", line=10)
    assert p10_rescues([a]) is False


# ---------------------------------------------------------------------------
# Merged from test_duplicate_tests_render.py
# ---------------------------------------------------------------------------


def _member(
    name: str, file: str = "tests/unit/test_foo.py", line: int = 1
) -> dict[str, object]:
    return {"name": name, "file": file, "line": line}


def _cluster(
    signal: str, names: list[str], file: str = "tests/unit/test_foo.py"
) -> dict[str, object]:
    return {"signal": signal, "members": [_member(n, file=file) for n in names]}


def test_text_renders_ambiguous_clusters() -> None:
    clusters = [
        _cluster(
            "ambiguous_distinct_literals", ["test_a", "test_b", "test_c", "test_d"]
        ),
    ]
    text = render_clusters_text(clusters)
    assert "cluster[ambiguous_distinct_literals]" in text
    for n in ("test_a", "test_b", "test_c", "test_d"):
        assert n in text


def test_text_orders_clusters_by_size_desc() -> None:
    clusters = [
        _cluster("signal3_x", [f"t6_{i}" for i in range(6)]),
        _cluster("ambiguous_distinct_literals", ["t2_0", "t2_1"]),
        _cluster("signal3_y", [f"t4_{i}" for i in range(4)]),
    ]
    text = render_clusters_text(clusters)
    lines = [ln for ln in text.splitlines() if ln.startswith("•")]
    assert "6 tests" in lines[0]
    assert "4 tests" in lines[1]
    assert "2 tests" in lines[2]


def test_text_includes_file_path_for_intra_file_cluster() -> None:
    clusters = [
        _cluster("signal3_x", ["test_a", "test_b"], file="tests/unit/test_foo.py"),
    ]
    text = render_clusters_text(clusters)
    assert "tests/unit/test_foo.py::" in text
    assert "test_a" in text
    assert "test_b" in text


def test_text_caps_at_max_text_clusters() -> None:
    total = _MAX_TEXT_CLUSTERS + 5
    clusters = []
    for i in range(total):
        sig = "ambiguous_distinct_literals" if i % 2 else "signal3_x"
        clusters.append(_cluster(sig, [f"t{i}_a", f"t{i}_b"]))
    text = render_clusters_text(clusters)
    bullet_lines = [ln for ln in text.splitlines() if ln.startswith("•")]
    assert len(bullet_lines) == _MAX_TEXT_CLUSTERS
    assert "(+5 more clusters)" in text


# ---------------------------------------------------------------------------
# Hash-based cluster acknowledgement (axm-1727)
# ---------------------------------------------------------------------------


def _raw_cluster(signal: str, tests: list[tuple[str, str, int]]) -> dict[str, Any]:
    """Build a raw cluster shaped like the ones fed to _slim_clusters."""
    return {
        "signal": signal,
        "similarity": 0.9,
        "members": [{"file": f, "name": n, "line": ln} for f, n, ln in tests],
    }


def test_cluster_hash_is_deterministic_and_order_independent() -> None:
    """AC1: same (file, name) members in different order → identical 12-char hash."""
    cluster_a = _raw_cluster(
        "signal1_call_assert",
        [
            ("tests/test_a.py", "test_x", 10),
            ("tests/test_b.py", "test_y", 20),
        ],
    )
    cluster_b = _raw_cluster(
        "signal1_call_assert",
        [
            ("tests/test_b.py", "test_y", 20),
            ("tests/test_a.py", "test_x", 10),
        ],
    )
    h_a = _cluster_hash(cluster_a)
    h_b = _cluster_hash(cluster_b)
    assert h_a == h_b
    assert len(h_a) == 12
    assert all(c in "0123456789abcdef" for c in h_a)


def test_cluster_hash_changes_when_member_added() -> None:
    """AC1: adding a member must change the hash (composition-stable contract)."""
    cluster_a = _raw_cluster(
        "signal1_call_assert",
        [
            ("tests/test_a.py", "test_x", 10),
            ("tests/test_b.py", "test_y", 20),
        ],
    )
    cluster_b = _raw_cluster(
        "signal1_call_assert",
        [
            ("tests/test_a.py", "test_x", 10),
            ("tests/test_b.py", "test_y", 20),
            ("tests/test_c.py", "test_z", 30),
        ],
    )
    assert _cluster_hash(cluster_a) != _cluster_hash(cluster_b)


def test_cluster_hash_ignores_line_field() -> None:
    """AC1: line drifts on every edit — must not invalidate acknowledgement."""
    cluster_a = _raw_cluster(
        "signal1_call_assert",
        [
            ("tests/test_a.py", "test_x", 10),
            ("tests/test_b.py", "test_y", 20),
        ],
    )
    cluster_b = _raw_cluster(
        "signal1_call_assert",
        [
            ("tests/test_a.py", "test_x", 999),
            ("tests/test_b.py", "test_y", 1),
        ],
    )
    assert _cluster_hash(cluster_a) == _cluster_hash(cluster_b)


def test_slim_clusters_attaches_hash_field() -> None:
    """AC1: every emitted cluster carries `cluster_hash` (12 hex chars)."""
    raw = _raw_cluster(
        "signal1_call_assert",
        [
            ("tests/test_a.py", "test_x", 10),
            ("tests/test_b.py", "test_y", 20),
        ],
    )
    slim = _slim_clusters([raw])  # type: ignore[list-item]
    assert len(slim) == 1
    out = slim[0]
    assert "cluster_hash" in out
    h = out["cluster_hash"]
    assert isinstance(h, str)
    assert len(h) == 12
    assert all(c in "0123456789abcdef" for c in h)


# ---------------------------------------------------------------------------
# Cluster payload dedup — members-only shape (axm-1728)
# ---------------------------------------------------------------------------


def test_slim_clusters_emits_members_only_no_tests_key() -> None:
    """AC1: _slim_clusters emits `members` only; `tests` key is absent."""
    raw = {
        "signal": "signal1_call_assert",
        "similarity": 0.9,
        "members": [
            {"file": "tests/test_a.py", "name": "test_x", "line": 10},
            {"file": "tests/test_b.py", "name": "test_y", "line": 20},
        ],
    }
    out = _slim_clusters([raw])  # type: ignore[list-item]
    assert len(out) == 1
    assert "members" in out[0]
    assert "tests" not in out[0]


def test_render_clusters_text_reads_members() -> None:
    """AC3: render_clusters_text renders both members from `members` key."""
    cluster = {
        "signal": "signal1_call_assert",
        "similarity": 0.9,
        "members": [
            {"file": "tests/test_a.py", "name": "test_x"},
            {"file": "tests/test_b.py", "name": "test_y"},
        ],
    }
    text = render_clusters_text([cluster])  # type: ignore[list-item]
    assert "tests/test_a.py::test_x" in text
    assert "tests/test_b.py::test_y" in text


def test_self_audit_payload_under_size_threshold() -> None:
    """AC5: self-audit cluster payload is < 65 000 chars after the dedup."""
    pkg_root = Path(__file__).resolve().parents[2]
    result = DuplicateTestsRule().check(pkg_root)
    payload = json.dumps(result.metadata["clusters"])
    assert len(payload) < 65_000


def test_no_cluster_dict_has_tests_key() -> None:
    """AC1, AC2: every cluster in metadata uses `members`, never `tests`."""
    pkg_root = Path(__file__).resolve().parents[2]
    result = DuplicateTestsRule().check(pkg_root)
    for cluster in result.metadata["clusters"]:
        assert "members" in cluster
        assert "tests" not in cluster
