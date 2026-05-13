from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.tools.graph import GraphTool


class TestExecutePkgWithText:
    def test_execute_pkg_json_has_text(self, fixture_pkg: Path) -> None:
        result = GraphTool().execute(path=str(fixture_pkg), format="json")
        assert result.success
        assert isinstance(result.text, str)
        assert "ast_graph" in result.text
        assert "nodes" in result.data
        assert isinstance(result.data["nodes"], list)

    def test_execute_pkg_mermaid_has_text(self, fixture_pkg: Path) -> None:
        result = GraphTool().execute(path=str(fixture_pkg), format="mermaid")
        assert result.success
        assert isinstance(result.text, str)
        assert "mermaid" in result.data

    def test_execute_pkg_text_has_text(self, fixture_pkg: Path) -> None:
        result = GraphTool().execute(path=str(fixture_pkg), format="text")
        assert result.success
        assert isinstance(result.text, str)
        assert "text" in result.data


class TestExecuteWsWithText:
    def test_execute_ws_json_has_text(self, fixture_ws: Path) -> None:
        result = GraphTool().execute(path=str(fixture_ws), format="json")
        assert result.success
        assert isinstance(result.text, str)
        assert "graph" in result.data

    def test_execute_ws_mermaid_has_text(self, fixture_ws: Path) -> None:
        result = GraphTool().execute(path=str(fixture_ws), format="mermaid")
        assert result.success
        assert isinstance(result.text, str)
        assert "mermaid" in result.data


@pytest.fixture
def fixture_pkg(tmp_path):
    """Minimal Python package for integration tests."""
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    src = pkg / "src" / "mypkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "cli.py").write_text("from mypkg.core import parser\n")
    core = src / "core"
    core.mkdir()
    (core / "__init__.py").write_text("")
    (core / "parser.py").write_text("from mypkg import utils\n")
    (core / "cache.py").write_text("")
    (src / "utils.py").write_text("")
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "mypkg"\nversion = "0.1.0"\n\n'
        '[build-system]\nrequires = ["hatchling"]\n'
        'build-backend = "hatchling.build"\n'
    )
    return pkg


@pytest.fixture
def fixture_ws(tmp_path):
    """Minimal uv workspace for integration tests."""
    ws = tmp_path / "myws"
    ws.mkdir()
    (ws / "pyproject.toml").write_text(
        '[project]\nname = "myws"\nversion = "0.1.0"\n\n'
        '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
    )
    pkgs = ws / "packages"
    pkgs.mkdir()
    for name, deps in [("pkg-a", ["pkg-b"]), ("pkg-b", []), ("pkg-c", ["pkg-a"])]:
        p = pkgs / name
        src = p / "src" / name.replace("-", "_")
        src.mkdir(parents=True)
        (src / "__init__.py").write_text("")
        dep_str = ", ".join(f'"{d}"' for d in deps)
        (p / "pyproject.toml").write_text(
            f'[project]\nname = "{name}"\nversion = "0.1.0"\n'
            f"dependencies = [{dep_str}]\n\n"
            '[build-system]\nrequires = ["hatchling"]\n'
            'build-backend = "hatchling.build"\n'
        )
    return ws
