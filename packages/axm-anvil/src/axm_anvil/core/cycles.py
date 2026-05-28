"""Import-cycle detection for the move pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["GraphEdits", "detect_new_cycle"]


@dataclass
class GraphEdits:
    """Edge additions and removals to apply to an import graph."""

    adds: list[tuple[str, str]] = field(default_factory=list)
    removes: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class _TarjanState:
    graph: dict[str, set[str]]
    index_counter: int = 0
    indices: dict[str, int] = field(default_factory=dict)
    lowlinks: dict[str, int] = field(default_factory=dict)
    on_stack: set[str] = field(default_factory=set)
    stack: list[str] = field(default_factory=list)
    sccs: list[list[str]] = field(default_factory=list)
    call_stack: list[tuple[str, list[str]]] = field(default_factory=list)


def _tarjan_step_descend(state: _TarjanState, v: str, succs: list[str]) -> None:
    """Visit one successor: push a new frame or update lowlink for a back-edge."""
    w = succs.pop(0)
    if w not in state.indices:
        state.indices[w] = state.index_counter
        state.lowlinks[w] = state.index_counter
        state.index_counter += 1
        state.stack.append(w)
        state.on_stack.add(w)
        state.call_stack.append((w, sorted(state.graph.get(w, set()))))
    elif w in state.on_stack:
        state.lowlinks[v] = min(state.lowlinks[v], state.indices[w])


def _tarjan_step_finalize(state: _TarjanState, v: str) -> None:
    """Pop the frame for ``v``; emit its SCC if root, propagate lowlink up."""
    if state.lowlinks[v] == state.indices[v]:
        scc: list[str] = []
        while True:
            w = state.stack.pop()
            state.on_stack.discard(w)
            scc.append(w)
            if w == v:
                break
        state.sccs.append(scc)
    state.call_stack.pop()
    if state.call_stack:
        parent = state.call_stack[-1][0]
        state.lowlinks[parent] = min(state.lowlinks[parent], state.lowlinks[v])


def _tarjan_sccs(graph: dict[str, set[str]]) -> list[list[str]]:
    """Iterative Tarjan SCC — never recurses to avoid stack blowups."""
    state = _TarjanState(graph=graph)
    for start in list(graph.keys()):
        if start in state.indices:
            continue
        state.indices[start] = state.index_counter
        state.lowlinks[start] = state.index_counter
        state.index_counter += 1
        state.stack.append(start)
        state.on_stack.add(start)
        state.call_stack.append((start, sorted(graph.get(start, set()))))
        while state.call_stack:
            v, succs = state.call_stack[-1]
            if succs:
                _tarjan_step_descend(state, v, succs)
            else:
                _tarjan_step_finalize(state, v)
    return state.sccs


def cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Return SCCs of size > 1 plus self-loops."""
    out: list[list[str]] = []
    for scc in _tarjan_sccs(graph):
        if len(scc) > 1:
            out.append(scc)
        elif len(scc) == 1 and scc[0] in graph.get(scc[0], set()):
            out.append(scc)
    return out


def _order_cycle(scc: list[str], graph: dict[str, set[str]]) -> list[str]:
    """Return scc nodes ordered along a directed walk for readable output."""
    if len(scc) == 1:
        return list(scc)
    scc_set = set(scc)
    start = min(scc)
    ordered = [start]
    visited = {start}
    current = start
    while len(ordered) < len(scc):
        nxt: str | None = None
        for cand in sorted(graph.get(current, set())):
            if cand in scc_set and cand not in visited:
                nxt = cand
                break
        if nxt is None:
            break
        ordered.append(nxt)
        visited.add(nxt)
        current = nxt
    return ordered


def detect_new_cycle(graph: dict[str, set[str]], edits: GraphEdits) -> list[str] | None:
    """Apply ``edits`` to a copy of ``graph`` and return the first newly
    introduced cycle, or ``None`` if the edits do not create any new cycle.

    Pre-existing cycles (already present in ``graph``) are ignored.
    """
    pre = {frozenset(c) for c in cycles(graph)}
    new_graph: dict[str, set[str]] = {k: set(v) for k, v in graph.items()}
    for src, dst in edits.removes:
        if src in new_graph:
            new_graph[src].discard(dst)
    for src, dst in edits.adds:
        new_graph.setdefault(src, set()).add(dst)
        new_graph.setdefault(dst, set())
    for scc in cycles(new_graph):
        if frozenset(scc) not in pre:
            return _order_cycle(scc, new_graph)
    return None
