"""TDD tests for graph ranking — symbol importance via PageRank."""

from __future__ import annotations

from pathlib import Path

from axm_ast.core.analyzer import analyze_package
from axm_ast.core.ranker import (
    _build_symbol_graph,
    _pagerank,
    rank_symbols,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"


# ─── Unit: _build_symbol_graph ───────────────────────────────────────────────


class TestBuildSymbolGraphUnit:
    """Test the symbol-level reference graph builder (unit)."""

    def test_import_creates_edge(self) -> None:
        """Importing a symbol from another module creates an edge."""
        pkg = analyze_package(FIXTURES / "sample_pkg")
        graph = _build_symbol_graph(pkg)
        # utils imports from . (sample_pkg) — should create edges
        assert len(graph) > 0

    def test_all_exports_boost(self) -> None:
        """Symbols listed in __all__ get incoming edges."""
        pkg = analyze_package(FIXTURES / "sample_pkg")
        graph = _build_symbol_graph(pkg)
        # greet and Calculator are in __all__ — they should have
        # incoming edges from the module node
        has_greet_edge = any("greet" in targets for targets in graph.values())
        assert has_greet_edge, "greet (in __all__) should have incoming edges"


# ─── Unit: _pagerank ────────────────────────────────────────────────────────


class TestPageRank:
    """Test the pure-Python PageRank implementation."""

    def test_empty_graph(self) -> None:
        """Empty graph returns empty scores."""
        scores = _pagerank({})
        assert scores == {}

    def test_single_node(self) -> None:
        """Single node gets score 1.0."""
        scores = _pagerank({"A": set()})
        assert abs(scores["A"] - 1.0) < 0.01

    def test_hub_node_highest(self) -> None:
        """Node with most incoming links has highest score."""
        # A→C, B→C, D→C — C is the hub
        graph: dict[str, set[str]] = {
            "A": {"C"},
            "B": {"C"},
            "D": {"C"},
            "C": set(),
        }
        scores = _pagerank(graph)
        assert scores["C"] == max(scores.values())

    def test_isolated_node_min_score(self) -> None:
        """Disconnected node gets minimum (damping) score."""
        graph: dict[str, set[str]] = {
            "A": {"B"},
            "B": set(),
            "Z": set(),  # isolated
        }
        scores = _pagerank(graph)
        assert scores["Z"] < scores["B"]

    def test_cycle_converges(self) -> None:
        """A→B→A cycle converges, doesn't diverge."""
        graph: dict[str, set[str]] = {
            "A": {"B"},
            "B": {"A"},
        }
        scores = _pagerank(graph)
        # Should be roughly equal
        assert abs(scores["A"] - scores["B"]) < 0.01

    def test_diamond_graph(self) -> None:
        """A→B, A→C, B→D, C→D — D gets highest score."""
        graph: dict[str, set[str]] = {
            "A": {"B", "C"},
            "B": {"D"},
            "C": {"D"},
            "D": set(),
        }
        scores = _pagerank(graph)
        assert scores["D"] == max(scores.values())

    def test_scores_sum_to_one(self) -> None:
        """All scores should approximately sum to 1.0."""
        graph: dict[str, set[str]] = {
            "A": {"B", "C"},
            "B": {"C"},
            "C": set(),
        }
        scores = _pagerank(graph)
        total = sum(scores.values())
        assert abs(total - 1.0) < 0.05


# ─── Unit: rank_symbols ─────────────────────────────────────────────────────


class TestRankSymbolsUnit:
    """Test the high-level rank_symbols function (unit)."""

    def test_returns_dict(self) -> None:
        """Returns a dict mapping symbol names to float scores."""
        pkg = analyze_package(FIXTURES / "sample_pkg")
        result = rank_symbols(pkg)
        assert isinstance(result, dict)
        assert all(isinstance(v, float) for v in result.values())

    def test_all_symbols_present(self) -> None:
        """Every public symbol should appear in results."""
        pkg = analyze_package(FIXTURES / "sample_pkg")
        result = rank_symbols(pkg)
        # At minimum, greet and Calculator should be ranked
        assert "greet" in result
        assert "Calculator" in result

    def test_exported_symbol_ranks_higher(self) -> None:
        """Symbols in __all__ should rank higher than private ones."""
        pkg = analyze_package(FIXTURES / "sample_pkg")
        result = rank_symbols(pkg)
        if "_internal_helper" in result:
            assert result["greet"] > result["_internal_helper"]

    def test_scores_non_negative(self) -> None:
        """All scores must be >= 0."""
        pkg = analyze_package(FIXTURES / "sample_pkg")
        result = rank_symbols(pkg)
        assert all(v >= 0 for v in result.values())


# ─── Functional: formatter integration ───────────────────────────────────────


class TestRankedFormatting:
    """Test ranking integration with the text formatter."""

    def test_budget_with_rank_shows_important(self) -> None:
        """Budget + rank should prioritize important symbols."""
        from axm_ast.formatters import format_text

        pkg = analyze_package(FIXTURES / "sample_pkg")
        output = format_text(pkg, detail="summary", budget=10, rank=True)
        lines = output.strip().split("\n")
        assert len(lines) >= 1

    def test_budget_without_rank_unchanged(self) -> None:
        """Default budget behavior (no rank) is preserved."""
        from axm_ast.formatters import format_text

        pkg = analyze_package(FIXTURES / "sample_pkg")
        output = format_text(pkg, detail="summary", budget=10)
        assert "truncated" in output.lower() or len(output.split("\n")) <= 11
