"""Integration tests for analyze_impact_workspace end-to-end behavior."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.mark.usefixtures("_mock_analyze_workspace")
class TestAnalyzeImpactWorkspace:
    """Verify analyze_impact_workspace output is unchanged after refactor."""

    def test_analyze_impact_workspace(self, workspace_path: Path) -> None:
        from axm_ast.core.impact import analyze_impact_workspace

        result = analyze_impact_workspace(workspace_path, "MySymbol")

        assert result["symbol"] == "MySymbol"
        assert result["workspace"] == "my-ws"
        assert "definition" in result
        assert "callers" in result
        assert "reexports" in result
        assert "affected_modules" in result
        assert "test_files" in result
        assert "score" in result

    def test_missing_workspace_root(self, tmp_path: Path) -> None:
        """analyze_impact_workspace with invalid path → graceful empty result."""
        from axm_ast.core.impact import analyze_impact_workspace

        invalid = tmp_path / "nonexistent"
        result = analyze_impact_workspace(invalid, "Foo")

        # Graceful: returns a valid dict with empty collections
        assert result["symbol"] == "Foo"
        assert isinstance(result["callers"], list)
        assert isinstance(result["score"], str)


@pytest.fixture()
def workspace_path(tmp_path: Path) -> Path:
    """Return a dummy workspace path for testing."""
    return tmp_path / "ws"


@pytest.fixture()
def _mock_analyze_workspace(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock analyze_workspace and its transitive deps for unit tests."""
    pkg = MagicMock()
    pkg.name = "my-pkg"
    ws = MagicMock()
    ws.name = "my-ws"
    ws.packages = [pkg]

    mock_aw = MagicMock(return_value=ws)
    monkeypatch.setattr(
        "axm_ast.core.impact.analyze_workspace",
        mock_aw,
    )

    # find_definition returns a simple dict
    monkeypatch.setattr(
        "axm_ast.core.impact.find_definition",
        MagicMock(return_value={"module": "mod", "line": 1}),
    )
    monkeypatch.setattr(
        "axm_ast.core.impact.find_callers_workspace",
        MagicMock(return_value=[]),
    )
    monkeypatch.setattr(
        "axm_ast.core.impact._collect_workspace_reexports",
        MagicMock(return_value=[]),
    )
    monkeypatch.setattr(
        "axm_ast.core.impact._collect_workspace_tests",
        MagicMock(return_value=[]),
    )
    monkeypatch.setattr(
        "axm_ast.core.impact._add_workspace_git_coupling",
        MagicMock(),
    )
    monkeypatch.setattr(
        "axm_ast.core.impact.score_impact",
        MagicMock(return_value="LOW"),
    )
    return mock_aw


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


class TestWorkspaceImpact:
    """Tests for analyze_impact_workspace."""

    def test_analyze_impact_workspace(self, workspace_root: Path) -> None:
        """Impact analysis finds cross-package callers."""
        from axm_ast.core.impact import analyze_impact_workspace

        result = analyze_impact_workspace(workspace_root, "helper")
        assert result["symbol"] == "helper"
        assert result["workspace"] == "test-workspace"
        assert "definition" in result
        assert "callers" in result
        assert "score" in result

    def test_analyze_impact_workspace_callers(self, workspace_root: Path) -> None:
        """Impact callers include cross-package references."""
        from axm_ast.core.impact import analyze_impact_workspace

        result = analyze_impact_workspace(workspace_root, "helper")
        caller_modules = [c["module"] for c in result["callers"]]
        assert any("pkg_b::" in m for m in caller_modules)
