"""Tests for workspace_patcher — root file patching after member scaffold."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.adapters.workspace_patcher import (
    patch_all,
    patch_ci,
    patch_makefile,
    patch_mkdocs,
    patch_publish,
    patch_pyproject,
)


@pytest.fixture()
def workspace_root(tmp_path: Path) -> Path:
    """Create a minimal workspace root structure."""
    root = tmp_path / "my-workspace"
    root.mkdir()

    # Makefile
    (root / "Makefile").write_text(
        ".PHONY: test-all lint-all\n\n"
        "test-all:\n\tuv run pytest packages/ -q\n\n"
        "lint-all:\n\tuv run ruff check packages/\n"
    )

    # mkdocs.yml
    (root / "mkdocs.yml").write_text(
        'site_name: "my-workspace"\n\n'
        "plugins:\n  - search\n  - monorepo\n\n"
        "nav:\n  - Home: index.md\n"
    )

    # pyproject.toml
    (root / "pyproject.toml").write_text(
        '[project]\nname = "my-workspace"\nversion = "0.1.0"\n\n'
        "dependencies = []\n\n"
        "[tool.uv.workspace]\n"
        'members = ["packages/*"]\n'
    )

    # .github/workflows/
    ci_dir = root / ".github" / "workflows"
    ci_dir.mkdir(parents=True)

    (ci_dir / "ci.yml").write_text(
        "name: CI\n\n"
        "jobs:\n  test:\n    strategy:\n      matrix:\n"
        "        package:\n          - existing-pkg\n"
        "    steps:\n      - uses: actions/checkout@v4\n"
    )

    (ci_dir / "publish.yml").write_text(
        "name: Publish\n\non:\n  push:\n    tags:\n"
        '      - "v*"\n\njobs:\n  publish:\n'
        "    runs-on: ubuntu-latest\n"
    )

    return root


class TestPatchMakefile:
    """Tests for patch_makefile."""

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


class TestPatchMkdocs:
    """Tests for patch_mkdocs."""

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


class TestPatchPyproject:
    """Tests for patch_pyproject."""

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


class TestPatchCi:
    """Tests for patch_ci."""

    def test_adds_package_to_matrix(self, workspace_root: Path) -> None:
        patch_ci(workspace_root, "my-lib")

        content = (workspace_root / ".github" / "workflows" / "ci.yml").read_text()
        assert "- my-lib" in content
        assert "- existing-pkg" in content

    def test_idempotent(self, workspace_root: Path) -> None:
        patch_ci(workspace_root, "my-lib")
        content1 = (workspace_root / ".github" / "workflows" / "ci.yml").read_text()
        patch_ci(workspace_root, "my-lib")
        content2 = (workspace_root / ".github" / "workflows" / "ci.yml").read_text()
        assert content1 == content2


class TestPatchPublish:
    """Tests for patch_publish."""

    def test_adds_tag_pattern(self, workspace_root: Path) -> None:
        patch_publish(workspace_root, "my-lib")

        content = (workspace_root / ".github" / "workflows" / "publish.yml").read_text()
        assert "my-lib/v*" in content

    def test_idempotent(self, workspace_root: Path) -> None:
        patch_publish(workspace_root, "my-lib")
        content1 = (
            workspace_root / ".github" / "workflows" / "publish.yml"
        ).read_text()
        patch_publish(workspace_root, "my-lib")
        content2 = (
            workspace_root / ".github" / "workflows" / "publish.yml"
        ).read_text()
        assert content1 == content2


class TestPatchAll:
    """Tests for patch_all orchestrator."""

    def test_patches_all_files(self, workspace_root: Path) -> None:
        patched = patch_all(workspace_root, "my-lib")
        assert len(patched) == 5
        assert "Makefile" in patched
        assert "mkdocs.yml" in patched
        assert "pyproject.toml" in patched

    def test_skips_missing_files(self, tmp_path: Path) -> None:
        """When no root files exist, patch_all returns empty list."""
        patched = patch_all(tmp_path, "my-lib")
        assert patched == []
