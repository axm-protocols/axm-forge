"""Tests for workspace-member template structure and TemplateType.MEMBER."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.core.templates import TemplateType, get_template_path


class TestMemberTemplateType:
    """Tests for TemplateType.MEMBER and get_template_path dispatch."""

    def test_member_template_path(self) -> None:
        path = get_template_path(TemplateType.MEMBER)
        assert path.name == "workspace-member"
        assert path.is_dir()

    def test_member_has_copier_yml(self) -> None:
        path = get_template_path(TemplateType.MEMBER)
        assert (path / "copier.yml").is_file()


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

    def test_pyproject_has_hatch_vcs(self, member_template: Path) -> None:
        content = (member_template / "pyproject.toml.jinja").read_text()
        assert "hatch-vcs" in content
        assert "tag-pattern" in content

    def test_pyproject_has_member_name(self, member_template: Path) -> None:
        content = (member_template / "pyproject.toml.jinja").read_text()
        assert "{{ member_name }}" in content

    def test_mkdocs_is_nav_only(self, member_template: Path) -> None:
        content = (member_template / "mkdocs.yml.jinja").read_text()
        assert "nav:" in content
        # Should NOT have theme/plugins — it's a nav-only config for !include
        assert "plugins:" not in content
