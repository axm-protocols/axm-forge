"""Tests for import graph edge resolution.

Complements test_analyzer.py with focused tests for _resolve_import_target
and _build_edges — verifying that absolute intra-package imports create edges.
"""

from pathlib import Path

from axm_ast.core.analyzer import analyze_package, build_import_graph


class TestAbsoluteImportEdges:
    """Absolute intra-package imports create dependency edges."""

    def test_absolute_import_creates_edge(self, tmp_path: Path) -> None:
        """from pkg.sub import X → edge (mod, sub)."""
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "sub.py").write_text("x = 1\n")
        (pkg / "main.py").write_text("from mypkg.sub import x\n")

        result = analyze_package(pkg)
        graph = build_import_graph(result)
        assert "main" in graph
        assert "sub" in graph["main"]

    def test_absolute_import_nested(self, tmp_path: Path) -> None:
        """from pkg.core.engine import X → edge (cli, core.engine)."""
        pkg = tmp_path / "mypkg"
        core = pkg / "core"
        core.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (core / "__init__.py").write_text("")
        (core / "engine.py").write_text("def run() -> None: ...\n")
        (pkg / "cli.py").write_text("from mypkg.core.engine import run\n")

        result = analyze_package(pkg)
        graph = build_import_graph(result)
        assert "cli" in graph
        assert "core.engine" in graph["cli"]

    def test_absolute_import_to_package_root(self, tmp_path: Path) -> None:
        """from pkg import X → edge (mod, pkg)."""
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("VERSION = '1.0'\n")
        (pkg / "info.py").write_text("from mypkg import VERSION\n")

        result = analyze_package(pkg)
        graph = build_import_graph(result)
        assert "info" in graph
        assert "mypkg" in graph["info"]

    def test_external_import_no_edge(self, tmp_path: Path) -> None:
        """from pathlib import Path → no edge."""
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("from pathlib import Path\nimport os\n")

        result = analyze_package(pkg)
        graph = build_import_graph(result)
        # No internal edges — both imports are external
        assert "mod" not in graph

    def test_self_import_no_edge(self, tmp_path: Path) -> None:
        """from pkg.mod import X inside mod.py → no self-loop."""
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("from mypkg.mod import something\n")

        result = analyze_package(pkg)
        graph = build_import_graph(result)
        # Should not have self-loop
        if "mod" in graph:
            assert "mod" not in graph["mod"]


class TestRelativeImportEdges:
    """Relative imports still create edges (regression test)."""

    def test_relative_import_creates_edge(self, tmp_path: Path) -> None:
        """from .sub import X → edge."""
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "sub.py").write_text("x = 1\n")
        (pkg / "main.py").write_text("from .sub import x\n")

        result = analyze_package(pkg)
        graph = build_import_graph(result)
        assert "main" in graph
        assert "sub" in graph["main"]


class TestMixedImports:
    """Packages using both absolute and relative imports."""

    def test_both_create_edges(self, tmp_path: Path) -> None:
        """Both import styles produce edges in the same graph."""
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "a.py").write_text("x = 1\n")
        (pkg / "b.py").write_text("y = 2\n")
        (pkg / "c.py").write_text("from .a import x\nfrom mypkg.b import y\n")

        result = analyze_package(pkg)
        graph = build_import_graph(result)
        assert "c" in graph
        targets = graph["c"]
        assert "a" in targets
        assert "b" in targets


class TestRealProjectGraph:
    """Smoke test on axm-ast source itself."""

    def test_axm_ast_has_edges(self) -> None:
        """axm_ast package must have import edges (not empty graph)."""
        src = Path(__file__).parent.parent / "src" / "axm_ast"
        if not src.is_dir():
            import pytest

            pytest.skip("Source not available")
        result = analyze_package(src)
        graph = build_import_graph(result)
        # cli.py imports from core.analyzer, formatters, etc.
        assert len(graph) > 0
        total_edges = sum(len(v) for v in graph.values())
        assert total_edges >= 1
