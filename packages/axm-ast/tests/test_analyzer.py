"""Test analyzer — package analysis, dependency graph, search."""

from pathlib import Path

import pytest

from axm_ast.core.analyzer import (
    _SKIP_DIRS,
    _discover_py_files,
    analyze_package,
    build_import_graph,
    get_public_api,
    search_symbols,
)
from axm_ast.models.nodes import (
    ClassInfo,
    FunctionInfo,
    FunctionKind,
    SymbolKind,
    VariableInfo,
)

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
            '"""Tiny package."""\ndef hi() -> str:\n    """Say hi."""\n    return "hi"'
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
        results = search_symbols(pkg, kind=SymbolKind.PROPERTY)
        assert len(results) >= 1
        assert all(
            isinstance(r, FunctionInfo) and r.kind == FunctionKind.PROPERTY
            for r in results
        )

    def test_search_by_kind_class(self):
        """kind=CLASS returns only ClassInfo items."""
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, kind=SymbolKind.CLASS)
        assert len(results) >= 1
        assert all(isinstance(r, ClassInfo) for r in results)

    def test_search_by_kind_function(self):
        """kind=FUNCTION returns only FunctionInfo items with kind=FUNCTION."""
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, kind=SymbolKind.FUNCTION)
        assert len(results) >= 1
        assert all(
            isinstance(r, FunctionInfo) and r.kind == FunctionKind.FUNCTION
            for r in results
        )
        names = [r.name for r in results]
        # No classes should be in results
        assert "Calculator" not in names

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

    def test_search_variable_by_name(self) -> None:
        """search_symbols finds module-level variables by name."""
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, name="MAX_RETRIES")
        assert len(results) >= 1
        match = [r for r in results if r.name == "MAX_RETRIES"]
        assert len(match) == 1
        assert isinstance(match[0], VariableInfo)
        assert match[0].line > 0

    def test_search_variable_kind_filter(self) -> None:
        """kind=VARIABLE returns only variables."""
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, kind=SymbolKind.VARIABLE)
        assert len(results) >= 1
        assert all(isinstance(r, VariableInfo) for r in results)
        names = [r.name for r in results]
        assert "MAX_RETRIES" in names
        assert "DEFAULT_NAME" in names
        # No functions or classes
        assert "greet" not in names
        assert "Calculator" not in names

    def test_search_kind_none_includes_variables(self) -> None:
        """kind=None returns functions, methods, AND variables."""
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg)
        names = [r.name for r in results]
        assert "greet" in names
        assert "MAX_RETRIES" in names

    def test_search_function_unchanged(self) -> None:
        """kind=FUNCTION still returns only functions."""
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, kind=SymbolKind.FUNCTION)
        assert len(results) >= 1
        assert all(isinstance(r, FunctionInfo) for r in results)
        names = [r.name for r in results]
        assert "greet" in names
        assert "MAX_RETRIES" not in names

    def test_search_class_unchanged(self) -> None:
        """kind=CLASS still returns only classes."""
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, kind=SymbolKind.CLASS)
        assert all(isinstance(r, ClassInfo) for r in results)
        names = [r.name for r in results]
        assert "Calculator" in names
        assert "MAX_RETRIES" not in names

    def test_search_annotated_variable(self) -> None:
        """Type-annotated constant is resolved with annotation."""
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, name="MAX_RETRIES")
        match = [r for r in results if r.name == "MAX_RETRIES"]
        assert len(match) == 1
        var = match[0]
        assert isinstance(var, VariableInfo)
        assert var.annotation == "int"


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


# ─── Gitignore-aware filtering ───────────────────────────────────────────────


class TestDiscoverGitignore:
    """Tests for gitignore-aware directory filtering in _discover_py_files."""

    def _init_git_repo(self, path: Path) -> None:
        """Initialise a minimal git repo so .gitignore is respected."""
        import subprocess

        subprocess.run(["git", "init", "-q"], cwd=path, check=True)

    def test_discover_skips_gitignored_dirs(self, tmp_path: Path) -> None:
        """Directories listed in .gitignore are excluded from discovery."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        self._init_git_repo(pkg)
        (pkg / ".gitignore").write_text("backup/\n")
        (pkg / "mod.py").write_text("x = 1")
        backup = pkg / "backup"
        backup.mkdir()
        (backup / "old.py").write_text("y = 2")

        found = _discover_py_files(pkg)
        names = [p.name for p in found]
        assert "mod.py" in names
        assert "old.py" not in names

    def test_discover_still_skips_hardcoded_dirs(self, tmp_path: Path) -> None:
        """Hardcoded _SKIP_DIRS are still skipped even without .gitignore."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("x = 1")
        cache = pkg / "__pycache__"
        cache.mkdir()
        (cache / "mod.cpython-312.py").write_text("")

        found = _discover_py_files(pkg)
        assert len(found) == 1
        assert found[0].name == "mod.py"

    def test_discover_works_outside_git_repo(self, tmp_path: Path) -> None:
        """Without a .git directory, falls back to _SKIP_DIRS only."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("x = 1")
        # "backup" is NOT in _SKIP_DIRS and there's no git repo
        backup = pkg / "backup"
        backup.mkdir()
        (backup / "extra.py").write_text("y = 2")
        # hardcoded skip dir still filtered
        venv = pkg / ".venv"
        venv.mkdir()
        (venv / "dep.py").write_text("z = 3")

        found = _discover_py_files(pkg)
        names = [p.name for p in found]
        assert "mod.py" in names
        assert "extra.py" in names  # not gitignored, not in _SKIP_DIRS
        assert "dep.py" not in names  # hardcoded skip

    def test_nested_gitignore_respected(self, tmp_path: Path) -> None:
        """A .gitignore at a subdirectory level is respected for that subtree."""
        pkg = tmp_path / "pkg"
        sub = pkg / "sub"
        sub.mkdir(parents=True)
        self._init_git_repo(pkg)
        (sub / ".gitignore").write_text("generated/\n")
        (pkg / "mod.py").write_text("x = 1")
        (sub / "ok.py").write_text("y = 2")
        gen = sub / "generated"
        gen.mkdir()
        (gen / "auto.py").write_text("z = 3")

        found = _discover_py_files(pkg)
        names = [p.name for p in found]
        assert "mod.py" in names
        assert "ok.py" in names
        assert "auto.py" not in names

    def test_no_git_dir_graceful_fallback(self, tmp_path: Path) -> None:
        """Non-git project gracefully falls back to _SKIP_DIRS."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("x = 1")
        # Even with a .gitignore file, no .git → ignore file has no effect
        (pkg / ".gitignore").write_text("data/\n")
        data = pkg / "data"
        data.mkdir()
        (data / "stuff.py").write_text("y = 2")

        found = _discover_py_files(pkg)
        names = [p.name for p in found]
        # No git repo → .gitignore not processed → data/ is discovered
        assert "stuff.py" in names
        assert "mod.py" in names


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
