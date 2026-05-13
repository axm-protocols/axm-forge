"""Registering a new member patches root Makefile, mkdocs, pyproject, testpaths."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.adapters.workspace_patcher import (
    patch_makefile,
    patch_mkdocs,
    patch_pyproject,
    patch_testpaths,
)


class TestMakefileGetsMemberTargets:
    """patch_makefile adds per-member test/lint targets."""

    def test_adds_targets(self, workspace_root: Path) -> None:
        patch_makefile(workspace_root, "my-lib")

        content = (workspace_root / "Makefile").read_text()
        assert "test-my-lib:" in content
        assert "lint-my-lib:" in content
        assert "--package my-lib" in content
        assert "packages/my-lib/src/my_lib/" in content

    def test_idempotent(self, workspace_root: Path) -> None:
        patch_makefile(workspace_root, "my-lib")
        content1 = (workspace_root / "Makefile").read_text()
        patch_makefile(workspace_root, "my-lib")
        content2 = (workspace_root / "Makefile").read_text()
        assert content1 == content2

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            patch_makefile(tmp_path, "my-lib")


class TestMkdocsGetsMemberInclude:
    """patch_mkdocs adds nav include for the new member's docs."""

    def test_adds_include(self, workspace_root: Path) -> None:
        patch_mkdocs(workspace_root, "my-lib")

        content = (workspace_root / "mkdocs.yml").read_text()
        assert "!include ./packages/my-lib/mkdocs.yml" in content
        assert "my-lib:" in content

    def test_idempotent(self, workspace_root: Path) -> None:
        patch_mkdocs(workspace_root, "my-lib")
        content1 = (workspace_root / "mkdocs.yml").read_text()
        patch_mkdocs(workspace_root, "my-lib")
        content2 = (workspace_root / "mkdocs.yml").read_text()
        assert content1 == content2


class TestPyprojectGetsMemberDependency:
    """patch_pyproject adds the member as a workspace dependency."""

    def test_adds_dependency_and_source(self, workspace_root: Path) -> None:
        patch_pyproject(workspace_root, "my-lib")

        content = (workspace_root / "pyproject.toml").read_text()
        assert '"my-lib"' in content
        assert "[tool.uv.sources.my-lib]" in content
        assert "workspace = true" in content

    def test_idempotent(self, workspace_root: Path) -> None:
        patch_pyproject(workspace_root, "my-lib")
        content1 = (workspace_root / "pyproject.toml").read_text()
        patch_pyproject(workspace_root, "my-lib")
        content2 = (workspace_root / "pyproject.toml").read_text()
        assert content1 == content2


class TestTestpathsGetsMemberEntry:
    """patch_testpaths registers the member's tests directory."""

    def test_adds_testpath(self, workspace_root: Path) -> None:
        patch_testpaths(workspace_root, "my-lib")

        content = (workspace_root / "pyproject.toml").read_text()
        assert "packages/my-lib/tests" in content
        assert "[tool.pytest.ini_options]" in content

    def test_idempotent(self, workspace_root: Path) -> None:
        patch_testpaths(workspace_root, "my-lib")
        content1 = (workspace_root / "pyproject.toml").read_text()
        patch_testpaths(workspace_root, "my-lib")
        content2 = (workspace_root / "pyproject.toml").read_text()
        assert content1 == content2

    def test_creates_section_if_absent(self, workspace_root: Path) -> None:
        content = (workspace_root / "pyproject.toml").read_text()
        assert "[tool.pytest.ini_options]" not in content

        patch_testpaths(workspace_root, "my-lib")

        content = (workspace_root / "pyproject.toml").read_text()
        assert "[tool.pytest.ini_options]" in content
        assert "packages/my-lib/tests" in content

    def test_adds_to_existing_testpaths(self, workspace_root: Path) -> None:
        pyproject = workspace_root / "pyproject.toml"
        content = pyproject.read_text()
        content += (
            "\n[tool.pytest.ini_options]\n"
            'testpaths = [\n    "packages/existing/tests",\n]\n'
        )
        pyproject.write_text(content)

        patch_testpaths(workspace_root, "my-lib")

        result = pyproject.read_text()
        assert "packages/existing/tests" in result
        assert "packages/my-lib/tests" in result
