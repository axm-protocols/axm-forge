"""Split from ``test_workspace.py``."""

from pathlib import Path

import pytest

from axm_ast.core.workspace import analyze_workspace


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


class TestCrossPackageCallers:
    """Tests for find_callers_workspace."""

    def test_find_callers_workspace(self, workspace_root: Path) -> None:
        """Find cross-package call to helper()."""
        from axm_ast.core.callers import find_callers_workspace

        ws = analyze_workspace(workspace_root)
        callers = find_callers_workspace(ws, "helper")

        # Should find the call in pkg_b::main
        assert len(callers) >= 1
        modules = [c.module for c in callers]
        assert any("pkg_b::" in m for m in modules)

    def test_find_callers_workspace_no_match(self, workspace_root: Path) -> None:
        """Symbol not called anywhere returns empty list."""
        from axm_ast.core.callers import find_callers_workspace

        ws = analyze_workspace(workspace_root)
        callers = find_callers_workspace(ws, "nonexistent_function")
        assert callers == []

    def test_find_callers_workspace_prefix_format(self, workspace_root: Path) -> None:
        """Module names use pkg_name::module_name format."""
        from axm_ast.core.callers import find_callers_workspace

        ws = analyze_workspace(workspace_root)
        callers = find_callers_workspace(ws, "helper")
        for c in callers:
            assert "::" in c.module
