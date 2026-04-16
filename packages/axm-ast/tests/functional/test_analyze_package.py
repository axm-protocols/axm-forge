"""Functional tests for analyze_package — public API boundary.

Covers module discovery, package naming, error handling,
directory filtering, and .gitignore support.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast import analyze_package
from axm_ast.core.analyzer import build_import_graph

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
SAMPLE_PKG = FIXTURES / "sample_pkg"


# ─── Core behavior ─────────────────────────────────────────────────────────


@pytest.mark.functional
class TestAnalyzePackage:
    """Tests for analyze_package()."""

    def test_discovers_all_modules(self):
        pkg = analyze_package(SAMPLE_PKG)
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


# ─── Directory filtering ───────────────────────────────────────────────────


@pytest.mark.functional
class TestAnalyzePackageFiltering:
    """Tests that analyze_package correctly filters skip dirs."""

    def test_skips_venv_dir(self, tmp_path):
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""My package."""')
        venv = pkg / ".venv" / "site-packages" / "dep"
        venv.mkdir(parents=True)
        (venv / "dep.py").write_text("class Dep: pass")

        result = analyze_package(pkg)
        assert len(result.modules) == 1
        assert result.modules[0].path.name == "__init__.py"

    def test_venv_not_in_graph(self, tmp_path):
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

    def test_skips_pycache(self, tmp_path):
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""pkg."""')
        (pkg / "mod.py").write_text("x = 1")
        cache = pkg / "__pycache__"
        cache.mkdir()
        (cache / "mod.cpython-312.py").write_text("")

        result = analyze_package(pkg)
        mod_names = [m.path.name for m in result.modules]
        assert "mod.py" in mod_names
        assert "mod.cpython-312.py" not in mod_names

    def test_skips_multiple_dirs(self, tmp_path):
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""pkg."""')
        for skip in (".venv", "node_modules", ".git"):
            d = pkg / skip
            d.mkdir()
            (d / "file.py").write_text("")

        result = analyze_package(pkg)
        assert len(result.modules) == 1

    def test_skips_egg_info(self, tmp_path):
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""pkg."""')
        egg = pkg / "foo.egg-info"
        egg.mkdir()
        (egg / "bar.py").write_text("")

        result = analyze_package(pkg)
        assert len(result.modules) == 1

    def test_nested_skip_dir(self, tmp_path):
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""pkg."""')
        (pkg / "mod.py").write_text("x = 1")
        sub = pkg / "sub"
        sub.mkdir()
        (sub / "__init__.py").write_text("")
        (sub / "ok.py").write_text("y = 2")
        cache = sub / ".mypy_cache"
        cache.mkdir()
        (cache / "cached.py").write_text("z = 3")

        result = analyze_package(pkg)
        mod_names = [m.path.name for m in result.modules]
        assert "ok.py" in mod_names
        assert "cached.py" not in mod_names

    def test_top_level_and_nested_venv_both_skipped(self, tmp_path):
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""pkg."""')
        (pkg / "mod.py").write_text("x = 1")
        (pkg / ".venv").mkdir()
        (pkg / ".venv" / "a.py").write_text("")
        sub = pkg / "sub"
        sub.mkdir()
        (sub / "__init__.py").write_text("")
        (sub / "ok.py").write_text("y = 2")
        (sub / ".venv").mkdir()
        (sub / ".venv" / "b.py").write_text("")

        result = analyze_package(pkg)
        mod_names = sorted(m.path.name for m in result.modules)
        assert "a.py" not in mod_names
        assert "b.py" not in mod_names


# ─── Gitignore support ─────────────────────────────────────────────────────


@pytest.mark.functional
class TestAnalyzePackageGitignore:
    """Tests that analyze_package respects .gitignore."""

    def _init_git_repo(self, path: Path) -> None:
        import subprocess

        subprocess.run(["git", "init", "-q"], cwd=path, check=True)

    def test_skips_gitignored_dirs(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        self._init_git_repo(pkg)
        (pkg / ".gitignore").write_text("backup/\n")
        (pkg / "__init__.py").write_text('"""pkg."""')
        (pkg / "mod.py").write_text("x = 1")
        backup = pkg / "backup"
        backup.mkdir()
        (backup / "old.py").write_text("y = 2")

        result = analyze_package(pkg)
        mod_names = [m.path.name for m in result.modules]
        assert "mod.py" in mod_names
        assert "old.py" not in mod_names

    def test_works_outside_git_repo(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""pkg."""')
        (pkg / "mod.py").write_text("x = 1")
        backup = pkg / "backup"
        backup.mkdir()
        (backup / "__init__.py").write_text("")
        (backup / "extra.py").write_text("y = 2")
        venv = pkg / ".venv"
        venv.mkdir()
        (venv / "dep.py").write_text("z = 3")

        result = analyze_package(pkg)
        mod_names = [m.path.name for m in result.modules]
        assert "mod.py" in mod_names
        assert "extra.py" in mod_names
        assert "dep.py" not in mod_names

    def test_nested_gitignore_respected(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypkg"
        sub = pkg / "sub"
        sub.mkdir(parents=True)
        self._init_git_repo(pkg)
        (pkg / "__init__.py").write_text('"""pkg."""')
        (sub / ".gitignore").write_text("generated/\n")
        (pkg / "mod.py").write_text("x = 1")
        (sub / "__init__.py").write_text("")
        (sub / "ok.py").write_text("y = 2")
        gen = sub / "generated"
        gen.mkdir()
        (gen / "auto.py").write_text("z = 3")

        result = analyze_package(pkg)
        mod_names = [m.path.name for m in result.modules]
        assert "mod.py" in mod_names
        assert "ok.py" in mod_names
        assert "auto.py" not in mod_names

    def test_no_git_dir_graceful_fallback(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""pkg."""')
        (pkg / "mod.py").write_text("x = 1")
        (pkg / ".gitignore").write_text("data/\n")
        data = pkg / "data"
        data.mkdir()
        (data / "__init__.py").write_text("")
        (data / "stuff.py").write_text("y = 2")

        result = analyze_package(pkg)
        mod_names = [m.path.name for m in result.modules]
        assert "stuff.py" in mod_names
        assert "mod.py" in mod_names
