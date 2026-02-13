"""Test analyzer — package analysis, dependency graph, search, stubs.

TDD: Tests written first, then analyzer.py implementation.
"""

from pathlib import Path

import pytest

from axm_ast.core.analyzer import (
    _SKIP_DIRS,
    _discover_py_files,
    analyze_package,
    build_import_graph,
    generate_stubs,
    get_public_api,
    search_symbols,
)
from axm_ast.models.nodes import FunctionInfo, FunctionKind

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_PKG = FIXTURES / "sample_pkg"


# ─── analyze_package ─────────────────────────────────────────────────────────


class TestAnalyzePackage:
    """Tests for analyze_package()."""

    def test_discovers_all_modules(self):
        pkg = analyze_package(SAMPLE_PKG)
        # Should find: __init__.py, utils.py, sub/__init__.py
        assert len(pkg.modules) >= 3

    def test_package_name(self):
        pkg = analyze_package(SAMPLE_PKG)
        assert pkg.name == "sample_pkg"

    def test_package_root(self):
        pkg = analyze_package(SAMPLE_PKG)
        assert pkg.root == SAMPLE_PKG.resolve()

    def test_module_names_populated(self):
        pkg = analyze_package(SAMPLE_PKG)
        assert len(pkg.module_names) >= 3

    def test_not_a_directory(self, tmp_path):
        fake = tmp_path / "not_a_dir.py"
        fake.write_text("x = 1")
        with pytest.raises(ValueError, match="not a directory"):
            analyze_package(fake)

    def test_no_python_files(self, tmp_path):
        empty_dir = tmp_path / "empty_pkg"
        empty_dir.mkdir()
        pkg = analyze_package(empty_dir)
        assert pkg.modules == []

    def test_single_file_package(self, tmp_path):
        """A directory with just __init__.py."""
        pkg_dir = tmp_path / "tiny"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Tiny package."""\n'
            "def hi() -> str:\n"
            '    """Say hi."""\n'
            '    return "hi"'
        )
        pkg = analyze_package(pkg_dir)
        assert len(pkg.modules) == 1
        assert len(pkg.modules[0].functions) == 1


# ─── build_import_graph ──────────────────────────────────────────────────────


class TestBuildImportGraph:
    """Tests for internal import graph construction."""

    def test_returns_dict(self):
        pkg = analyze_package(SAMPLE_PKG)
        graph = build_import_graph(pkg)
        assert isinstance(graph, dict)

    def test_detects_relative_import(self):
        """utils.py imports from . (relative), should appear as edge."""
        pkg = analyze_package(SAMPLE_PKG)
        graph = build_import_graph(pkg)
        # graph should have at least one edge
        all_edges = []
        for src, targets in graph.items():
            for t in targets:
                all_edges.append((src, t))
        assert len(all_edges) >= 1


# ─── get_public_api ──────────────────────────────────────────────────────────


class TestGetPublicApi:
    """Tests for public API extraction."""

    def test_returns_list(self):
        pkg = analyze_package(SAMPLE_PKG)
        api = get_public_api(pkg)
        assert isinstance(api, list)

    def test_only_public_symbols(self):
        pkg = analyze_package(SAMPLE_PKG)
        api = get_public_api(pkg)
        names = [item.name for item in api]
        # greet and Calculator are in __all__
        assert "greet" in names
        assert "Calculator" in names
        # _internal_helper should not be in public API
        assert "_internal_helper" not in names


# ─── search_symbols ──────────────────────────────────────────────────────────


class TestSearchSymbols:
    """Tests for semantic search across a package."""

    def test_search_by_name(self):
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, name="greet")
        assert len(results) >= 1
        assert results[0].name == "greet"

    def test_search_by_return_type(self):
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, returns="str")
        names = [r.name for r in results]
        assert "greet" in names

    def test_search_by_kind(self):
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, kind=FunctionKind.PROPERTY)
        assert len(results) >= 1
        assert all(
            isinstance(r, FunctionInfo) and r.kind == FunctionKind.PROPERTY
            for r in results
        )

    def test_search_no_results(self):
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, name="nonexistent_xyz")
        assert results == []

    def test_search_by_base_class(self):
        """Search for classes inheriting from a specific base."""
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, inherits="BaseModel")
        # No class inherits BaseModel in fixtures, should be empty
        assert results == []


# ─── generate_stubs ──────────────────────────────────────────────────────────


class TestGenerateStubs:
    """Tests for .pyi-like stub generation."""

    def test_returns_string(self):
        pkg = analyze_package(SAMPLE_PKG)
        stubs = generate_stubs(pkg)
        assert isinstance(stubs, str)
        assert len(stubs) > 0

    def test_contains_function_signatures(self):
        pkg = analyze_package(SAMPLE_PKG)
        stubs = generate_stubs(pkg)
        assert "def greet" in stubs

    def test_contains_class(self):
        pkg = analyze_package(SAMPLE_PKG)
        stubs = generate_stubs(pkg)
        assert "class Calculator" in stubs

    def test_no_implementation_details(self):
        """Stubs should not contain function bodies."""
        pkg = analyze_package(SAMPLE_PKG)
        stubs = generate_stubs(pkg)
        assert "return" not in stubs


# ─── _discover_py_files (unit tests) ─────────────────────────────────────────


class TestDiscoverPyFiles:
    """Unit tests for _discover_py_files."""

    def test_discover_skips_venv(self, tmp_path):
        """Files inside .venv/ are not discovered."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("x = 1")
        venv = pkg / ".venv" / "lib"
        venv.mkdir(parents=True)
        (venv / "dep.py").write_text("y = 2")

        found = _discover_py_files(pkg)
        names = [p.name for p in found]
        assert "mod.py" in names
        assert "dep.py" not in names

    def test_discover_skips_pycache(self, tmp_path):
        """Files inside __pycache__/ are not discovered."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("x = 1")
        cache = pkg / "__pycache__"
        cache.mkdir()
        (cache / "mod.cpython-312.py").write_text("")

        found = _discover_py_files(pkg)
        assert len(found) == 1
        assert found[0].name == "mod.py"

    def test_discover_skips_multiple(self, tmp_path):
        """Multiple skip dirs are all filtered out."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("x = 1")
        for skip in (".venv", "node_modules", ".git"):
            d = pkg / skip
            d.mkdir()
            (d / "file.py").write_text("")

        found = _discover_py_files(pkg)
        assert len(found) == 1
        assert found[0].name == "mod.py"

    def test_discover_skips_egg_info(self, tmp_path):
        """Directories ending with .egg-info are skipped."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("x = 1")
        egg = pkg / "foo.egg-info"
        egg.mkdir()
        (egg / "bar.py").write_text("")

        found = _discover_py_files(pkg)
        assert len(found) == 1

    def test_discover_keeps_nested_modules(self, tmp_path):
        """Legitimate nested subpackages are fully discovered."""
        pkg = tmp_path / "pkg"
        deep = pkg / "sub" / "deep"
        deep.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "sub" / "__init__.py").write_text("")
        (deep / "__init__.py").write_text("")
        (deep / "mod.py").write_text("x = 1")

        found = _discover_py_files(pkg)
        assert len(found) == 4

    def test_discover_empty_dir(self, tmp_path):
        """Empty directory returns nothing."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        assert _discover_py_files(pkg) == []


# ─── analyze_package + skip dirs (functional tests) ─────────────────────────


class TestAnalyzePackageSkipDirs:
    """Functional tests: analyze_package respects _SKIP_DIRS."""

    def test_analyze_skips_venv_dir(self, tmp_path):
        """Modules inside .venv are not included in PackageInfo."""
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""My package."""')
        venv = pkg / ".venv" / "site-packages" / "dep"
        venv.mkdir(parents=True)
        (venv / "dep.py").write_text("class Dep: pass")

        result = analyze_package(pkg)
        assert len(result.modules) == 1
        assert result.modules[0].path.name == "__init__.py"

    def test_analyze_venv_not_in_graph(self, tmp_path):
        """Venv modules must not appear in the dependency graph."""
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""My package."""')
        venv = pkg / ".venv" / "lib"
        venv.mkdir(parents=True)
        (venv / "dep.py").write_text("x = 1")

        result = analyze_package(pkg)
        graph = build_import_graph(result)
        all_nodes = set(graph.keys())
        for targets in graph.values():
            all_nodes.update(targets)
        assert not any("dep" in n for n in all_nodes)

    def test_analyze_real_project_scale(self):
        """Self-test: analyzing axm-ast source has < 50 modules."""
        src = Path(__file__).parent.parent / "src" / "axm_ast"
        if not src.is_dir():
            pytest.skip("Source not available")
        result = analyze_package(src)
        # Sanity: no venv leak
        assert len(result.modules) < 50


# ─── Edge cases ──────────────────────────────────────────────────────────────


class TestDiscoverEdgeCases:
    """Edge cases for directory filtering."""

    def test_venv_named_with_real_code_is_skipped(self, tmp_path):
        """A dir literally named 'venv' is skipped (convention)."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "app.py").write_text("x = 1")
        (pkg / "venv").mkdir()
        (pkg / "venv" / "real_module.py").write_text("y = 2")

        found = _discover_py_files(pkg)
        assert len(found) == 1

    def test_nested_skip_dir(self, tmp_path):
        """Skip dirs at any depth are filtered."""
        pkg = tmp_path / "pkg"
        sub = pkg / "sub" / ".mypy_cache"
        sub.mkdir(parents=True)
        (pkg / "mod.py").write_text("x = 1")
        (pkg / "sub" / "ok.py").write_text("y = 2")
        (sub / "cached.py").write_text("z = 3")

        found = _discover_py_files(pkg)
        names = [p.name for p in found]
        assert "mod.py" in names
        assert "ok.py" in names
        assert "cached.py" not in names

    def test_skip_dirs_constant_completeness(self):
        """Key directories are in the skip set."""
        for name in (
            ".venv",
            "venv",
            "__pycache__",
            ".git",
            "node_modules",
            ".tox",
            ".nox",
        ):
            assert name in _SKIP_DIRS

    def test_top_level_and_nested_venv_both_skipped(self, tmp_path):
        """Skip .venv whether at root or nested."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("x = 1")
        # Top-level .venv
        (pkg / ".venv").mkdir()
        (pkg / ".venv" / "a.py").write_text("")
        # Nested .venv inside subpackage
        sub = pkg / "sub"
        sub.mkdir()
        (sub / "ok.py").write_text("y = 2")
        (sub / ".venv").mkdir()
        (sub / ".venv" / "b.py").write_text("")

        found = _discover_py_files(pkg)
        names = [p.name for p in found]
        assert sorted(names) == ["mod.py", "ok.py"]
