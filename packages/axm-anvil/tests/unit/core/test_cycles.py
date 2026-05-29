from __future__ import annotations

from axm_anvil.core.cycles import GraphEdits, cycles, detect_new_cycle


def test_detect_new_cycle_none_on_clean_graph() -> None:
    graph: dict[str, set[str]] = {"a": {"b"}, "b": set(), "c": set()}
    edits = GraphEdits(adds=[("b", "c")], removes=[])
    assert detect_new_cycle(graph, edits) is None


def test_detect_new_cycle_returns_ordered_chain() -> None:
    graph: dict[str, set[str]] = {"a": {"b"}, "b": set()}
    edits = GraphEdits(adds=[("b", "a")], removes=[])
    cycle = detect_new_cycle(graph, edits)
    assert cycle is not None
    assert set(cycle) == {"a", "b"}
    assert len(cycle) == 2


def test_detect_new_cycle_ignores_preexisting_cycle() -> None:
    graph: dict[str, set[str]] = {
        "x": {"y"},
        "y": {"x"},
        "a": set(),
        "b": set(),
    }
    edits = GraphEdits(adds=[("a", "b")], removes=[])
    assert detect_new_cycle(graph, edits) is None


def test_detect_new_cycle_self_loop() -> None:
    graph: dict[str, set[str]] = {"a": set()}
    edits = GraphEdits(adds=[("a", "a")], removes=[])
    assert detect_new_cycle(graph, edits) == ["a"]


def test_detect_new_cycle_multi_hop() -> None:
    graph: dict[str, set[str]] = {"a": {"b"}, "b": {"c"}, "c": set()}
    edits = GraphEdits(adds=[("c", "a")], removes=[])
    cycle = detect_new_cycle(graph, edits)
    assert cycle is not None
    assert set(cycle) == {"a", "b", "c"}


def test_cycles_deep_chain_does_not_recurse() -> None:
    n = 10_000
    graph: dict[str, set[str]] = {str(i): {str(i + 1)} for i in range(n)}
    graph[str(n)] = set()

    result = cycles(graph)

    assert result == []


def test_cycles_simple_two_node_cycle() -> None:
    graph: dict[str, set[str]] = {"a": {"b"}, "b": {"a"}}

    result = cycles(graph)

    assert len(result) == 1
    assert set(result[0]) == {"a", "b"}


def test_cycles_no_cycle_returns_empty() -> None:
    graph: dict[str, set[str]] = {"a": {"b"}, "b": {"c"}, "c": set()}

    result = cycles(graph)

    assert result == []


def test_detect_new_cycle_cross_package_namespaced() -> None:
    """AC2, AC4: detect_new_cycle works on namespaced {import_pkg}.{module} nodes.

    A workspace graph already has ``pkg_a.x -> pkg_b.y``. Adding the reverse
    edge ``pkg_b.y -> pkg_a.x`` (what a cross-package move would introduce)
    must surface the new cycle ``[pkg_a.x, pkg_b.y]``. A pre-existing cycle
    in the same namespaced coordinates must be ignored.
    """
    graph: dict[str, set[str]] = {"pkg_a.x": {"pkg_b.y"}, "pkg_b.y": set()}
    edits = GraphEdits(adds=[("pkg_b.y", "pkg_a.x")], removes=[])

    cycle = detect_new_cycle(graph, edits)

    assert cycle is not None
    assert set(cycle) == {"pkg_a.x", "pkg_b.y"}
    assert len(cycle) == 2

    # AC4: a pre-existing cross-package cycle is not re-flagged.
    preexisting: dict[str, set[str]] = {
        "pkg_a.x": {"pkg_b.y"},
        "pkg_b.y": {"pkg_a.x"},
        "pkg_c.z": set(),
    }
    no_new = GraphEdits(adds=[("pkg_c.z", "pkg_a.x")], removes=[])
    assert detect_new_cycle(preexisting, no_new) is None
