from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.analyzer import (
    _resolve_absolute_import,
    analyze_package,
)
from axm_ast.core.parser import extract_module_info
from axm_ast.tools.graph import GraphTool

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def src_layout_pkg(tmp_path: Path) -> Path:
    """Create a minimal src-layout package with two modules importing each other."""
    pkg_dir = tmp_path / "src" / "mypkg"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "core.py").write_text("from mypkg import models\n")
    (pkg_dir / "models.py").write_text("from mypkg import core\n")
    return tmp_path


@pytest.fixture()
def flat_layout_pkg(tmp_path: Path) -> Path:
    """Create a minimal flat-layout package (no src/ dir)."""
    pkg_dir = tmp_path / "flatpkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "alpha.py").write_text("from flatpkg import beta\n")
    (pkg_dir / "beta.py").write_text("from flatpkg import alpha\n")
    return pkg_dir


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_resolve_absolute_import_src_layout() -> None:
    """_resolve_absolute_import strips real pkg_name prefix correctly."""
    result = _resolve_absolute_import(
        "axm_ast.core", "axm_ast", {"core", "models"}, "cli"
    )
    assert result == "core"


def test_resolve_absolute_import_src_layout_no_match() -> None:
    """_resolve_absolute_import returns None for unrelated package."""
    result = _resolve_absolute_import(
        "other_pkg.core", "axm_ast", {"core", "models"}, "cli"
    )
    assert result is None


def test_build_edges_src_layout(src_layout_pkg: Path) -> None:
    """_build_edges returns non-empty edges for a src-layout package."""
    src_dir = src_layout_pkg / "src" / "mypkg"
    py_files = sorted(src_dir.rglob("*.py"))
    _ = [extract_module_info(f) for f in py_files]

    # root passed to _build_edges should be what analyze_package would pass
    pkg = analyze_package(src_layout_pkg)
    edges = pkg.dependency_edges
    assert len(edges) > 0, "Expected non-empty edges for src-layout package"


def test_analyze_package_src_layout_name(src_layout_pkg: Path) -> None:
    """analyze_package sets pkg.name to the actual package name, not 'src'."""
    pkg = analyze_package(src_layout_pkg)
    assert pkg.name != "src", "pkg.name must not be 'src'"
    assert pkg.name == "mypkg"


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------

AXM_AST_PATH = str(
    Path(__file__).resolve().parents[2]  # tests/core/.. -> axm-ast root
)


@pytest.mark.functional()
def test_graph_tool_src_layout_has_edges() -> None:
    """GraphTool on axm-ast (src-layout) returns a graph with edges."""
    result = GraphTool().execute(path=AXM_AST_PATH)
    assert result.success, f"GraphTool failed: {result.error}"
    graph = result.data["graph"]
    has_edges = any(len(targets) > 0 for targets in graph.values())
    assert has_edges, "Expected at least one key with non-empty adjacency list"


@pytest.mark.functional()
def test_mermaid_src_layout_has_edges() -> None:
    """GraphTool mermaid output for src-layout contains edges."""
    result = GraphTool().execute(path=AXM_AST_PATH, format="mermaid")
    assert result.success, f"GraphTool failed: {result.error}"
    assert " --> " in result.data["mermaid"], "Mermaid output should contain edges"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_flat_layout_package(flat_layout_pkg: Path) -> None:
    """Flat-layout package: name is the directory name, edges resolve normally."""
    pkg = analyze_package(flat_layout_pkg)
    assert pkg.name == "flatpkg"
    assert len(pkg.dependency_edges) > 0, "Flat-layout should still produce edges"


def test_src_layout_multiple_packages(tmp_path: Path) -> None:
    """src-layout with two package dirs should pick the primary
    one or handle gracefully.
    """
    src = tmp_path / "src"
    src.mkdir()
    (src / "pkg_a").mkdir()
    (src / "pkg_a" / "__init__.py").write_text("")
    (src / "pkg_a" / "mod.py").write_text("x = 1\n")
    (src / "pkg_b").mkdir()
    (src / "pkg_b" / "__init__.py").write_text("")
    (src / "pkg_b" / "mod.py").write_text("y = 2\n")

    pkg = analyze_package(tmp_path)
    # Should not be "src"
    assert pkg.name != "src"


def test_namespace_package_no_init(tmp_path: Path) -> None:
    """src-layout but no __init__.py in child falls through to flat-layout behavior."""
    src = tmp_path / "src"
    src.mkdir()
    ns_pkg = src / "nspkg"
    ns_pkg.mkdir()
    # No __init__.py — namespace package
    (ns_pkg / "mod.py").write_text("x = 1\n")

    pkg = analyze_package(tmp_path)
    # Without __init__.py, src-layout detection should not trigger
    # so it falls through to treating tmp_path itself as the package
    assert pkg.name != "src"
