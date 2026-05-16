"""Tests for workspace scaffold template and TemplateType."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.core.templates import TemplateType, get_template_path


@pytest.mark.parametrize(
    ("template_type", "expected_name"),
    [
        pytest.param(TemplateType.WORKSPACE, "uv-workspace", id="workspace"),
        pytest.param(TemplateType.MEMBER, "workspace-member", id="member"),
    ],
)
def test_template_path_resolves_to_named_directory(
    template_type: TemplateType, expected_name: str
) -> None:
    path = get_template_path(template_type)
    assert path.name == expected_name
    assert path.is_dir()


@pytest.mark.parametrize(
    "template_type",
    [
        pytest.param(TemplateType.WORKSPACE, id="workspace"),
        pytest.param(TemplateType.MEMBER, id="member"),
    ],
)
def test_template_has_copier_yml(template_type: TemplateType) -> None:
    path = get_template_path(template_type)
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


class TestMemberTemplateStructure:
    """Verify workspace-member template includes all required files."""

    @pytest.fixture()
    def member_template(self) -> Path:
        return get_template_path(TemplateType.MEMBER)

    def test_root_files(self, member_template: Path) -> None:
        for name in [
            "copier.yml",
            "pyproject.toml.jinja",
            "README.md.jinja",
            "CONTRIBUTING.md.jinja",
            "mkdocs.yml.jinja",
        ]:
            assert (member_template / name).exists(), f"Missing {name}"

    def test_src_files(self, member_template: Path) -> None:
        src = member_template / "src" / "{{module_name}}"
        assert (src / "__init__.py.jinja").is_file()
        assert (src / "py.typed").is_file()

    def test_test_files(self, member_template: Path) -> None:
        tests = member_template / "tests"
        assert (tests / "__init__.py").is_file()
        assert (tests / "conftest.py").is_file()

    def test_docs_files(self, member_template: Path) -> None:
        assert (member_template / "docs" / "index.md.jinja").is_file()

    @pytest.mark.parametrize(
        "needle",
        [
            pytest.param("hatch-vcs", id="hatch_vcs"),
            pytest.param("tag-pattern", id="tag_pattern"),
            pytest.param("{{ member_name }}", id="member_name"),
        ],
    )
    def test_pyproject_contains(self, member_template: Path, needle: str) -> None:
        content = (member_template / "pyproject.toml.jinja").read_text()
        assert needle in content

    def test_mkdocs_is_nav_only(self, member_template: Path) -> None:
        content = (member_template / "mkdocs.yml.jinja").read_text()
        assert "nav:" in content
        # Should NOT have theme/plugins — it's a nav-only config for !include
        assert "plugins:" not in content
