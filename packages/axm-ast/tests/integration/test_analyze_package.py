"""Split from ``test_analyze_package__build_import_graph.py``.

Tests covering only ``analyze_package`` (no ``build_import_graph``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast import analyze_package


def _make_src_layout(root: Path, pkg_name: str = "mypkg") -> Path:
    """Create a minimal src-layout package and return the project root."""
    pkg_dir = root / "src" / pkg_name
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "core.py").write_text("def greet():\n    return 'hi'\n")
    return root


@pytest.mark.functional
def test_analyze_package_src_layout_root(tmp_path: Path) -> None:
    """analyze_package sets root inside src/ for src-layout packages."""
    _make_src_layout(tmp_path)
    pkg = analyze_package(tmp_path)
    assert pkg.root != tmp_path, "root should not be the project directory"
    assert tmp_path / "src" == pkg.root or pkg.root.is_relative_to(tmp_path / "src"), (
        f"root {pkg.root} should be inside src/"
    )


@pytest.mark.functional
def test_src_layout_name(tmp_path: Path) -> None:
    """analyze_package sets pkg.name to the actual package name, not 'src'."""
    _make_src_layout(tmp_path)
    pkg = analyze_package(tmp_path)
    assert pkg.name != "src", "pkg.name must not be 'src'"
    assert pkg.name == "mypkg"


@pytest.mark.functional
def test_flat_layout_package(tmp_path: Path) -> None:
    """Flat-layout package: name is the directory name, edges resolve normally."""
    pkg_dir = tmp_path / "flatpkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "alpha.py").write_text("from flatpkg import beta\n")
    (pkg_dir / "beta.py").write_text("from flatpkg import alpha\n")

    pkg = analyze_package(pkg_dir)
    assert pkg.name == "flatpkg"
    assert len(pkg.dependency_edges) > 0, "Flat-layout should still produce edges"


@pytest.mark.functional
def test_src_layout_multiple_packages(tmp_path: Path) -> None:
    """src-layout with two package dirs should handle gracefully."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "pkg_a").mkdir()
    (src / "pkg_a" / "__init__.py").write_text("")
    (src / "pkg_a" / "mod.py").write_text("x = 1\n")
    (src / "pkg_b").mkdir()
    (src / "pkg_b" / "__init__.py").write_text("")
    (src / "pkg_b" / "mod.py").write_text("y = 2\n")

    pkg = analyze_package(tmp_path)
    assert pkg.name != "src"


@pytest.mark.functional
def test_namespace_package_no_init(tmp_path: Path) -> None:
    """src-layout but no __init__.py in child falls through to flat-layout behavior."""
    src = tmp_path / "src"
    src.mkdir()
    ns_pkg = src / "nspkg"
    ns_pkg.mkdir()
    (ns_pkg / "mod.py").write_text("x = 1\n")

    pkg = analyze_package(tmp_path)
    assert pkg.name != "src"


@pytest.mark.integration
def test_build_edges_src_layout(tmp_path: Path) -> None:
    """analyze_package returns non-empty dependency_edges for a src-layout package."""
    pkg_dir = tmp_path / "src" / "mypkg"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "core.py").write_text("from mypkg import models\n")
    (pkg_dir / "models.py").write_text("from mypkg import core\n")

    pkg = analyze_package(tmp_path)
    assert len(pkg.dependency_edges) > 0, (
        "Expected non-empty edges for src-layout package"
    )


@pytest.mark.functional
class TestAnalyzePackageIntegration:
    """Tests for analyze_package() (real filesystem I/O scenarios)."""

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


@pytest.mark.functional
def test_skips_venv_dir(tmp_path):
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""My package."""')
    venv = pkg / ".venv" / "site-packages" / "dep"
    venv.mkdir(parents=True)
    (venv / "dep.py").write_text("class Dep: pass")

    result = analyze_package(pkg)
    assert len(result.modules) == 1
    assert result.modules[0].path.name == "__init__.py"


@pytest.mark.functional
def test_skips_pycache(tmp_path):
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


@pytest.mark.functional
def test_skips_multiple_dirs(tmp_path):
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""pkg."""')
    for skip in (".venv", "node_modules", ".git"):
        d = pkg / skip
        d.mkdir()
        (d / "file.py").write_text("")

    result = analyze_package(pkg)
    assert len(result.modules) == 1


@pytest.mark.functional
def test_skips_egg_info(tmp_path):
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""pkg."""')
    egg = pkg / "foo.egg-info"
    egg.mkdir()
    (egg / "bar.py").write_text("")

    result = analyze_package(pkg)
    assert len(result.modules) == 1


@pytest.mark.functional
def test_nested_skip_dir(tmp_path):
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


@pytest.mark.functional
def test_top_level_and_nested_venv_both_skipped(tmp_path):
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
