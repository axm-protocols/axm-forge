from __future__ import annotations

from axm_anvil.core.cycles import GraphEdits, _cycles, detect_new_cycle


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

    result = _cycles(graph)

    assert result == []


def test_cycles_simple_two_node_cycle() -> None:
    graph: dict[str, set[str]] = {"a": {"b"}, "b": {"a"}}

    result = _cycles(graph)

    assert len(result) == 1
    assert set(result[0]) == {"a", "b"}


def test_cycles_no_cycle_returns_empty() -> None:
    graph: dict[str, set[str]] = {"a": {"b"}, "b": {"c"}, "c": set()}

    result = _cycles(graph)

    assert result == []
