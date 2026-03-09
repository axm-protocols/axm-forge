"""Tests for workspace scaffold template and TemplateType."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.core.templates import TemplateType, get_template_path


class TestTemplateType:
    """Tests for TemplateType enum and get_template_path dispatch."""

    def test_standalone_is_default(self) -> None:
        path = get_template_path()
        assert path.name == "python-project"
        assert path.is_dir()

    def test_workspace_template_path(self) -> None:
        path = get_template_path(TemplateType.WORKSPACE)
        assert path.name == "uv-workspace"
        assert path.is_dir()

    def test_standalone_explicit(self) -> None:
        path = get_template_path(TemplateType.STANDALONE)
        assert path.name == "python-project"

    def test_workspace_has_copier_yml(self) -> None:
        path = get_template_path(TemplateType.WORKSPACE)
        assert (path / "copier.yml").is_file()


class TestWorkspaceTemplateStructure:
    """Verify workspace template includes all required files."""

    @pytest.fixture()
    def ws_template(self) -> Path:
        return get_template_path(TemplateType.WORKSPACE)

    def test_root_files(self, ws_template: Path) -> None:
        for name in [
            "copier.yml",
            "pyproject.toml.jinja",
            "Makefile",
            "README.md.jinja",
            "CONTRIBUTING.md.jinja",
            ".gitignore",
            ".pre-commit-config.yaml",
            "cliff.toml",
        ]:
            assert (ws_template / name).exists(), f"Missing {name}"

    def test_docs_files(self, ws_template: Path) -> None:
        assert (ws_template / "mkdocs.yml.jinja").is_file()
        assert (ws_template / "docs" / "index.md.jinja").is_file()
        assert (ws_template / "docs" / "gen_ref_pages.py").is_file()

    def test_ci_workflows(self, ws_template: Path) -> None:
        ci = ws_template / ".github" / "workflows"
        for name in [
            "ci.yml.jinja",
            "publish.yml",
            "docs.yml",
            "release.yml",
            "axm-quality.yml",
            "pre-commit-autoupdate.yml",
        ]:
            assert (ci / name).exists(), f"Missing CI workflow: {name}"

    def test_dependabot(self, ws_template: Path) -> None:
        assert (ws_template / ".github" / "dependabot.yml").is_file()

    def test_pyproject_has_workspace_config(self, ws_template: Path) -> None:
        content = (ws_template / "pyproject.toml.jinja").read_text()
        assert "[tool.uv.workspace]" in content
        assert 'members = ["packages/*"]' in content

    def test_mkdocs_has_monorepo(self, ws_template: Path) -> None:
        content = (ws_template / "mkdocs.yml.jinja").read_text()
        assert "monorepo" in content

    def test_ci_uses_package_flag(self, ws_template: Path) -> None:
        ci = ws_template / ".github" / "workflows" / "ci.yml.jinja"
        content = ci.read_text()
        assert "--package" in content
