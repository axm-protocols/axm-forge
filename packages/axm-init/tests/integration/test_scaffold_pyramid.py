"""Integration tests: scaffolded projects expose the 3-level test pyramid."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from axm_init.tools.check import InitCheckTool
from axm_init.tools.scaffold import InitScaffoldTool

pytestmark = pytest.mark.integration


def _scaffold_standalone(project_path: Path) -> None:
    result = InitScaffoldTool().execute(
        path=str(project_path),
        name=project_path.name,
        org="DemoOrg",
        author="Demo Author",
        email="demo@example.com",
        license="MIT",
        description="demo package",
    )
    assert result.success, result.error


def test_scaffold_python_project_creates_pyramid(tmp_path: Path) -> None:
    project = tmp_path / "demo-pkg"
    project.mkdir()
    _scaffold_standalone(project)

    for sub in ("unit", "integration", "e2e"):
        sub_dir = project / "tests" / sub
        assert sub_dir.is_dir(), f"Expected tests/{sub}/ to exist"
        assert (sub_dir / "__init__.py").is_file()
        assert (sub_dir / "conftest.py").is_file()
    assert (project / "tests" / "unit" / "test_version.py").is_file()


def test_scaffold_workspace_member_creates_pyramid(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    ws_result = InitScaffoldTool().execute(
        path=str(workspace),
        name="ws",
        org="DemoOrg",
        author="Demo Author",
        email="demo@example.com",
        license="MIT",
        description="demo workspace",
        workspace=True,
    )
    assert ws_result.success, ws_result.error

    member_result = InitScaffoldTool().execute(
        path=str(workspace),
        member="member-pkg",
        org="DemoOrg",
        author="Demo Author",
        email="demo@example.com",
        license="MIT",
        description="member pkg",
    )
    assert member_result.success, member_result.error

    member = workspace / "packages" / "member-pkg"
    for sub in ("unit", "integration", "e2e"):
        sub_dir = member / "tests" / sub
        assert sub_dir.is_dir(), f"Expected tests/{sub}/ to exist"
        assert (sub_dir / "__init__.py").is_file()
        assert (sub_dir / "conftest.py").is_file()


def test_scaffolded_pyproject_declares_markers(tmp_path: Path) -> None:
    project = tmp_path / "demo-pkg"
    project.mkdir()
    _scaffold_standalone(project)

    pyproject = project / "pyproject.toml"
    config = tomllib.loads(pyproject.read_text())
    markers = config["tool"]["pytest"]["ini_options"]["markers"]
    joined = "\n".join(markers)
    assert "integration" in joined
    assert "e2e" in joined


def test_scaffold_then_check_passes_structure_tests_dir(tmp_path: Path) -> None:
    project = tmp_path / "demo-pkg"
    project.mkdir()
    _scaffold_standalone(project)

    check = InitCheckTool().execute(path=str(project))
    assert check.success, check.error

    failed_names = {f["name"] for f in check.data["failed"]}
    assert "structure.tests_dir" not in failed_names, (
        f"structure.tests_dir failed: {check.data['failed']}"
    )
