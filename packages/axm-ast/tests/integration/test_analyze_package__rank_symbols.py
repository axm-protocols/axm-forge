"""Integration tests for graph ranking — split from tests/unit/test_ranker.py."""

from __future__ import annotations

from pathlib import Path

from axm_ast.core.analyzer import analyze_package
from axm_ast.core.ranker import rank_symbols


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
