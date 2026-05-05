from __future__ import annotations

from axm_audit.core.rules.test_quality.duplicate_tests import (
    _MAX_TEXT_CLUSTERS,
    render_clusters_text,
)


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
