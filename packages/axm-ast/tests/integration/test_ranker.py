"""Integration tests for graph ranking — split from tests/unit/test_ranker.py."""

from __future__ import annotations

from pathlib import Path

from axm_ast.core.analyzer import analyze_package
from axm_ast.core.ranker import _build_symbol_graph, rank_symbols


class TestBuildSymbolGraphIntegration:
    """Test the symbol-level reference graph builder (integration)."""

    def test_empty_package(self, tmp_path: Path) -> None:
        """An empty package produces an empty graph."""
        pkg_dir = tmp_path / "empty"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text('"""Empty."""')
        pkg = analyze_package(pkg_dir)
        graph = _build_symbol_graph(pkg)
        # Module node exists but has no symbol edges
        assert all(targets == set() for targets in graph.values())

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
            '"""Self ref."""\ndef foo() -> None:\n    """Foo."""\n    pass\n'
        )
        pkg = analyze_package(pkg_dir)
        graph = _build_symbol_graph(pkg)
        for source, targets in graph.items():
            assert source not in targets, f"self-loop on {source}"


class TestRankSymbolsIntegration:
    """Test the high-level rank_symbols function (integration)."""

    def test_empty_package(self, tmp_path: Path) -> None:
        """Empty package returns empty dict."""
        pkg_dir = tmp_path / "empty"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text('"""Empty."""')
        pkg = analyze_package(pkg_dir)
        result = rank_symbols(pkg)
        assert result == {}


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
        # Should complete without hanging; both symbols must be ranked
        assert "func_a" in result or "a.func_a" in result
        assert "func_b" in result or "b.func_b" in result
