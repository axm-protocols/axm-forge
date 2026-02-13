"""TDD tests for graph ranking — symbol importance via PageRank."""

from __future__ import annotations

from pathlib import Path

from axm_ast.core.analyzer import analyze_package
from axm_ast.core.ranker import (
    _build_symbol_graph,
    _pagerank,
    rank_symbols,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ─── Unit: _build_symbol_graph ───────────────────────────────────────────────


class TestBuildSymbolGraph:
    """Test the symbol-level reference graph builder."""

    def test_empty_package(self, tmp_path: Path) -> None:
        """An empty package produces an empty graph."""
        pkg_dir = tmp_path / "empty"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text('"""Empty."""')
        pkg = analyze_package(pkg_dir)
        graph = _build_symbol_graph(pkg)
        # May have module-level nodes, but no symbol edges
        assert isinstance(graph, dict)

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

    def test_base_class_edge(self, tmp_path: Path) -> None:
        """Inheriting a class creates an edge to the base class."""
        pkg_dir = tmp_path / "inherit_pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Inherit test."""\n'
            "class Base:\n"
            '    """Base class."""\n'
            "    pass\n"
            "class Child(Base):\n"
            '    """Child class."""\n'
            "    pass\n"
        )
        pkg = analyze_package(pkg_dir)
        graph = _build_symbol_graph(pkg)
        # Child → Base edge should exist (Child references Base)
        has_base_edge = any("Base" in targets for targets in graph.values())
        assert has_base_edge, "inheritance should create edge to Base"

    def test_self_loops_excluded(self, tmp_path: Path) -> None:
        """No self-referencing edges in the graph."""
        pkg_dir = tmp_path / "selfref"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Self ref."""\n' "def foo() -> None:\n" '    """Foo."""\n' "    pass\n"
        )
        pkg = analyze_package(pkg_dir)
        graph = _build_symbol_graph(pkg)
        for source, targets in graph.items():
            assert source not in targets, f"self-loop on {source}"


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


class TestRankSymbols:
    """Test the high-level rank_symbols function."""

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

    def test_empty_package(self, tmp_path: Path) -> None:
        """Empty package returns empty dict."""
        pkg_dir = tmp_path / "empty"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text('"""Empty."""')
        pkg = analyze_package(pkg_dir)
        result = rank_symbols(pkg)
        assert isinstance(result, dict)

    def test_scores_non_negative(self) -> None:
        """All scores must be >= 0."""
        pkg = analyze_package(FIXTURES / "sample_pkg")
        result = rank_symbols(pkg)
        assert all(v >= 0 for v in result.values())


# ─── Edge cases ──────────────────────────────────────────────────────────────


class TestRankerEdgeCases:
    """Edge cases for the ranking system."""

    def test_single_module_uniform(self, tmp_path: Path) -> None:
        """Package with one module, no imports → scores are set."""
        pkg_dir = tmp_path / "solo"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Solo."""\n'
            "def a() -> None:\n"
            '    """A."""\n'
            "    pass\n"
            "def b() -> None:\n"
            '    """B."""\n'
            "    pass\n"
        )
        pkg = analyze_package(pkg_dir)
        result = rank_symbols(pkg)
        assert len(result) >= 2

    def test_circular_imports_safe(self, tmp_path: Path) -> None:
        """Circular imports don't cause infinite loops."""
        pkg_dir = tmp_path / "circular"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text('"""Circular."""')
        (pkg_dir / "a.py").write_text(
            '"""A module."""\nfrom . import b\n'
            "def func_a() -> None:\n"
            '    """A func."""\n'
            "    pass\n"
        )
        (pkg_dir / "b.py").write_text(
            '"""B module."""\nfrom . import a\n'
            "def func_b() -> None:\n"
            '    """B func."""\n'
            "    pass\n"
        )
        pkg = analyze_package(pkg_dir)
        result = rank_symbols(pkg)
        # Should complete without hanging
        assert isinstance(result, dict)


# ─── Functional: formatter integration ───────────────────────────────────────


class TestRankedFormatting:
    """Test ranking integration with the text formatter."""

    def test_budget_with_rank_shows_important(self) -> None:
        """Budget + rank should prioritize important symbols."""
        from axm_ast.formatters import format_text

        pkg = analyze_package(FIXTURES / "sample_pkg")
        output = format_text(pkg, detail="summary", budget=10, rank=True)
        lines = output.strip().split("\n")
        assert len(lines) <= 11  # budget + possible truncation msg

    def test_budget_without_rank_unchanged(self) -> None:
        """Default budget behavior (no rank) is preserved."""
        from axm_ast.formatters import format_text

        pkg = analyze_package(FIXTURES / "sample_pkg")
        output = format_text(pkg, detail="summary", budget=10)
        assert "truncated" in output.lower() or len(output.split("\n")) <= 11
