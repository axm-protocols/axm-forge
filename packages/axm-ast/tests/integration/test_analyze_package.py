"""Functional tests for src-layout support in analyze_package."""

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
