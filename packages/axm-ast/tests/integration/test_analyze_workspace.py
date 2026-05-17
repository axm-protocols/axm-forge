"""Tests for workspace multi-package support.

Covers: detection, analysis, cross-package callers, impact,
context, dep graph, mermaid formatting, and edge cases.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.workspace import (
    analyze_workspace,
)

# ─── Fixtures ────────────────────────────────────────────────────────────────


def _make_pyproject(path: Path, name: str, deps: list[str] | None = None) -> None:
    """Write a minimal pyproject.toml for a workspace member."""
    dep_lines = ""
    if deps:
        dep_strs = ", ".join(f'"{d}"' for d in deps)
        dep_lines = f"dependencies = [{dep_strs}]"
    else:
        dep_lines = "dependencies = []"

    path.write_text(
        f"""\
[project]
name = "{name}"
version = "0.1.0"
{dep_lines}
""",
        encoding="utf-8",
    )


def _make_workspace(
    root: Path,
    members: list[str],
    *,
    ws_name: str = "test-workspace",
) -> None:
    """Create a workspace root pyproject.toml."""
    member_strs = ", ".join(f'"{m}"' for m in members)
    (root / "pyproject.toml").write_text(
        f"""\
[project]
name = "{ws_name}"
version = "0.1.0"

[tool.uv.workspace]
members = [{member_strs}]
""",
        encoding="utf-8",
    )


def _make_member_package(
    root: Path,
    member_name: str,
    *,
    src_layout: bool = True,
    deps: list[str] | None = None,
    py_files: dict[str, str] | None = None,
) -> Path:
    """Create a workspace member with a source package.

    Returns the path to the member directory.
    """
    member_dir = root / member_name
    member_dir.mkdir(parents=True, exist_ok=True)

    # pyproject.toml
    _make_pyproject(member_dir / "pyproject.toml", member_name, deps)

    # Package name = member_name with dashes replaced by underscores
    pkg_name = member_name.replace("-", "_")

    if src_layout:
        pkg_dir = member_dir / "src" / pkg_name
    else:
        pkg_dir = member_dir / pkg_name

    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")

    if py_files:
        for fname, content in py_files.items():
            (pkg_dir / fname).write_text(content, encoding="utf-8")

    return member_dir


@pytest.fixture()
def workspace_root(tmp_path: Path) -> Path:
    """Create a 2-package workspace with cross-package calls."""
    _make_workspace(tmp_path, ["pkg-a", "pkg-b"])

    # pkg-a: defines a function `helper()`
    _make_member_package(
        tmp_path,
        "pkg-a",
        py_files={
            "core.py": 'def helper():\n    """A helper function."""\n    return 42\n',
        },
    )

    # pkg-b: calls `helper()` from pkg-a
    pkg_b_main = "from pkg_a.core import helper\n\ndef run():\n    return helper()\n"
    _make_member_package(
        tmp_path,
        "pkg-b",
        deps=["pkg-a"],
        py_files={
            "main.py": pkg_b_main,
        },
    )

    return tmp_path


def test_analyze_workspace_parses_all(workspace_root: Path) -> None:
    """Analyze workspace finds both packages."""
    ws = analyze_workspace(workspace_root)
    assert len(ws.packages) >= 1
    pkg_names = {p.name for p in ws.packages}
    assert "pkg_a" in pkg_names
    assert "pkg_b" in pkg_names


def test_analyze_workspace_has_modules(workspace_root: Path) -> None:
    """Each package has the expected modules."""
    ws = analyze_workspace(workspace_root)
    for pkg in ws.packages:
        assert len(pkg.modules) > 0


def test_analyze_workspace_not_workspace(tmp_path: Path) -> None:
    """Raises ValueError for non-workspace path."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "single"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        analyze_workspace(tmp_path)


def test_missing_member_skipped(tmp_path: Path) -> None:
    """Workspace member that doesn't exist is skipped gracefully."""
    _make_workspace(tmp_path, ["exists", "missing"])
    _make_member_package(tmp_path, "exists")
    # Don't create "missing" directory

    ws = analyze_workspace(tmp_path)
    assert len(ws.packages) >= 1
    assert ws.packages[0].name == "exists"


def test_member_without_src_flat_layout(tmp_path: Path) -> None:
    """Member with flat layout (no src/) is still analyzed."""
    _make_workspace(tmp_path, ["flat-pkg"])
    _make_member_package(tmp_path, "flat-pkg", src_layout=False)

    ws = analyze_workspace(tmp_path)
    assert len(ws.packages) == 1
    assert ws.packages[0].name == "flat_pkg"


def test_single_member_workspace(tmp_path: Path) -> None:
    """Single-member workspace still works."""
    _make_workspace(tmp_path, ["only-pkg"])
    _make_member_package(tmp_path, "only-pkg")

    ws = analyze_workspace(tmp_path)
    assert len(ws.packages) >= 1


def test_member_without_python_source(tmp_path: Path) -> None:
    """Member without any Python package is skipped."""
    _make_workspace(tmp_path, ["no-python"])
    member_dir = tmp_path / "no-python"
    member_dir.mkdir()
    _make_pyproject(member_dir / "pyproject.toml", "no-python")
    # No src/ or package directory with __init__.py

    ws = analyze_workspace(tmp_path)
    assert len(ws.packages) == 0


def test_analyze_workspace_glob_members(tmp_path: Path) -> None:
    """analyze_workspace expands glob members and discovers packages."""
    (tmp_path / "pyproject.toml").write_text(
        '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
    )
    pkg_src = tmp_path / "packages" / "pkg-a" / "src" / "pkg_a"
    pkg_src.mkdir(parents=True)
    (pkg_src / "__init__.py").write_text("")
    (tmp_path / "packages" / "pkg-a" / "pyproject.toml").write_text(
        '[project]\nname = "pkg-a"\nversion = "0.1.0"\ndependencies = []\n'
    )

    ws = analyze_workspace(tmp_path)
    assert len(ws.packages) > 0
    pkg_names = [p.name for p in ws.packages]
    assert "pkg_a" in pkg_names
