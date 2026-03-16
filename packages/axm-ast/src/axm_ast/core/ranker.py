"""Symbol importance ranking via PageRank.

Scores every symbol in a package by "importance" using a PageRank-like
algorithm on the symbol reference graph. Symbols that are more imported,
exported (``__all__``), or inherited rank higher.

Example:
    >>> from axm_ast.core.ranker import rank_symbols
    >>> scores = rank_symbols(pkg)
    >>> sorted(scores, key=scores.get, reverse=True)[:5]
    ['Calculator', 'greet', 'resolve_path', ...]
"""

from __future__ import annotations

import logging

from axm_ast.models.nodes import (
    ModuleInfo,
    PackageInfo,
)

logger = logging.getLogger(__name__)

__all__ = [
    "rank_symbols",
]


# ─── Symbol graph builder ───────────────────────────────────────────────────


def _build_symbol_graph(pkg: PackageInfo) -> dict[str, set[str]]:
    """Build a symbol-level reference graph from the package.

    Edges represent "A references B":
    - Module → symbols it exports via ``__all__``
    - Child class → Base class (inheritance edge)
    - Importing module → symbols it imports from other modules

    Args:
        pkg: Analyzed package info.

    Returns:
        Adjacency dict mapping symbol name → set of referenced symbols.
    """
    graph: dict[str, set[str]] = {}
    all_symbol_names = _collect_all_symbols(pkg)

    for mod in pkg.modules:
        mod_node = _module_key(mod, pkg)
        graph.setdefault(mod_node, set())

        # __all__ exports: module → each exported symbol
        _add_all_export_edges(mod, mod_node, all_symbol_names, graph)

        # Inheritance: Child → Base
        _add_inheritance_edges(mod, all_symbol_names, graph)

        # Import edges: importing module → imported names
        _add_import_edges(mod, mod_node, all_symbol_names, graph)

        # Ensure every symbol is a node (even if no edges)
        _ensure_symbol_nodes(mod, graph)

    # Remove self-loops
    for source in graph:
        graph[source].discard(source)

    return graph


def _collect_all_symbols(pkg: PackageInfo) -> set[str]:
    """Collect all symbol names across the package."""
    names: set[str] = set()
    for mod in pkg.modules:
        for fn in mod.functions:
            names.add(fn.name)
        for cls in mod.classes:
            names.add(cls.name)
    return names


def _module_key(mod: ModuleInfo, pkg: PackageInfo) -> str:
    """Create a unique key for a module node."""
    try:
        rel = mod.path.relative_to(pkg.root)
    except ValueError:
        return f"__mod__{mod.path.stem}"
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    name = ".".join(parts) if parts else pkg.name
    return f"__mod__{name}"


def _add_all_export_edges(
    mod: ModuleInfo,
    mod_node: str,
    all_symbols: set[str],
    graph: dict[str, set[str]],
) -> None:
    """Add edges from module to its __all__ exports."""
    if mod.all_exports is None:
        return
    for export_name in mod.all_exports:
        if export_name in all_symbols:
            graph.setdefault(mod_node, set()).add(export_name)


def _add_inheritance_edges(
    mod: ModuleInfo,
    all_symbols: set[str],
    graph: dict[str, set[str]],
) -> None:
    """Add edges from child classes to base classes."""
    for cls in mod.classes:
        for base in cls.bases:
            if base in all_symbols:
                graph.setdefault(cls.name, set()).add(base)


def _add_import_edges(
    mod: ModuleInfo,
    mod_node: str,
    all_symbols: set[str],
    graph: dict[str, set[str]],
) -> None:
    """Add edges from importing module to imported symbol names."""
    for imp in mod.imports:
        if imp.is_relative:
            for name in imp.names:
                if name in all_symbols:
                    graph.setdefault(mod_node, set()).add(name)


def _ensure_symbol_nodes(
    mod: ModuleInfo,
    graph: dict[str, set[str]],
) -> None:
    """Ensure every function/class has a node in the graph."""
    for fn in mod.functions:
        graph.setdefault(fn.name, set())
    for cls in mod.classes:
        graph.setdefault(cls.name, set())


# ─── PageRank ────────────────────────────────────────────────────────────────


def _pagerank(
    graph: dict[str, set[str]],
    damping: float = 0.85,
    iterations: int = 30,
) -> dict[str, float]:
    """Compute PageRank scores for a directed graph.

    Pure-Python implementation without external dependencies.
    Edges go from ``source → target`` meaning source *references* target,
    so target receives the rank boost.

    Args:
        graph: Adjacency dict (node → set of nodes it points to).
        damping: Damping factor (typically 0.85).
        iterations: Number of power-iteration steps.

    Returns:
        Dict mapping node → importance score (sums to ~1.0).
    """
    nodes = list(graph.keys())
    n = len(nodes)
    if n == 0:
        return {}

    incoming, out_degree = _build_reverse_graph(graph, nodes)
    scores = _iterate_pagerank(nodes, incoming, out_degree, damping, iterations)
    return _normalize_scores(scores)


def _build_reverse_graph(
    graph: dict[str, set[str]],
    nodes: list[str],
) -> tuple[dict[str, list[str]], dict[str, int]]:
    """Build reverse graph (incoming edges) and out-degree counts."""
    incoming: dict[str, list[str]] = {node: [] for node in nodes}
    out_degree: dict[str, int] = dict.fromkeys(nodes, 0)

    for source, targets in graph.items():
        valid_targets = [t for t in targets if t in incoming]
        out_degree[source] = len(valid_targets)
        for target in valid_targets:
            incoming[target].append(source)

    return incoming, out_degree


def _iterate_pagerank(
    nodes: list[str],
    incoming: dict[str, list[str]],
    out_degree: dict[str, int],
    damping: float,
    iterations: int,
) -> dict[str, float]:
    """Run PageRank power iterations."""
    n = len(nodes)
    scores: dict[str, float] = dict.fromkeys(nodes, 1.0 / n)
    base = (1.0 - damping) / n

    for _ in range(iterations):
        new_scores: dict[str, float] = {}
        for node in nodes:
            rank_sum = sum(
                scores[src] / out_degree[src]
                for src in incoming[node]
                if out_degree[src] > 0
            )
            new_scores[node] = base + damping * rank_sum
        scores = new_scores

    return scores


def _normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    """Normalize scores so they sum to 1.0."""
    total = sum(scores.values())
    if total > 0:
        return {k: v / total for k, v in scores.items()}
    return scores


# ─── High-level API ──────────────────────────────────────────────────────────


def rank_symbols(pkg: PackageInfo) -> dict[str, float]:
    """Rank all symbols in a package by importance.

    Uses PageRank on the symbol reference graph to score each
    function and class. Higher scores mean the symbol is more
    referenced/exported.

    Args:
        pkg: Analyzed package info.

    Returns:
        Dict mapping symbol name → importance score.

    Example:
        >>> scores = rank_symbols(pkg)
        >>> top = sorted(scores, key=scores.get, reverse=True)
        >>> top[0]
        'Calculator'
    """
    graph = _build_symbol_graph(pkg)
    all_scores = _pagerank(graph)

    # Filter to only function/class symbols (not module nodes)
    symbol_names = _collect_all_symbols(pkg)
    result = {name: score for name, score in all_scores.items() if name in symbol_names}

    return result
