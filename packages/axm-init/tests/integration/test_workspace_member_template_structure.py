"""Unit tests for member gold-standard template (pure structure assertions, no I/O)."""

from __future__ import annotations

from pathlib import Path

import pytest

# Template root = src/axm_init/templates/workspace-member/
TEMPLATE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "axm_init"
    / "templates"
    / "workspace-member"
)
MKDOCS = (TEMPLATE_ROOT / "mkdocs.yml.jinja").read_text()

DOCS_DIR = TEMPLATE_ROOT / "docs"
DOCS_INDEX = (DOCS_DIR / "index.md.jinja").read_text()
README = (TEMPLATE_ROOT / "README.md.jinja").read_text()

COPIER_YML = (TEMPLATE_ROOT / "copier.yml").read_text()


class TestMemberMkdocsDiataxis:
    """mkdocs.yml must have Diátaxis nav structure."""

    @pytest.mark.parametrize(
        "needle",
        [
            pytest.param("Tutorials:", id="tutorials_section"),
            pytest.param("How-To", id="howto_section"),
            pytest.param("Reference:", id="reference_section"),
            pytest.param("Explanation:", id="explanation_section"),
        ],
    )
    def test_contains(self, needle: str) -> None:
        assert needle in MKDOCS


class TestMemberMkdocsInheritsFromRoot:
    """Workspace-member mkdocs.yml must not redeclare blocks set at root."""

    @pytest.mark.parametrize(
        "forbidden",
        [
            pytest.param("plugins:", id="no_plugins_block"),
            pytest.param("theme:", id="no_theme_block"),
            pytest.param("site_url:", id="no_site_url"),
            pytest.param("repo_url:", id="no_repo_url"),
        ],
    )
    def test_no_block(self, forbidden: str) -> None:
        assert forbidden not in MKDOCS


class TestMemberDocsIndex:
    """docs/index.md must follow workspace-member standard."""

    @pytest.mark.parametrize(
        "needle",
        [
            pytest.param("{{ member_name }}", id="has_member_name_heading"),
            pytest.param("{{ description }}", id="has_description"),
            pytest.param("## Installation", id="has_install_section"),
            pytest.param("## Quick Start", id="has_quick_start"),
            pytest.param("## Features", id="has_features"),
            pytest.param("axm-init.json", id="has_axm_init_badge"),
            pytest.param("axm-audit.json", id="has_axm_audit_badge"),
        ],
    )
    def test_contains(self, needle: str) -> None:
        assert needle in DOCS_INDEX

    def test_has_cta_buttons(self) -> None:
        assert "Get Started" in DOCS_INDEX
        assert "Reference" in DOCS_INDEX

    def test_uses_workspace_badge_paths(self) -> None:
        """Badge URLs must use workspace_name/member_name path pattern."""
        assert "{{ workspace_name }}" in DOCS_INDEX
        assert "{{ member_name }}/axm-init.json" in DOCS_INDEX


class TestMemberReadme:
    """README.md must follow workspace-member standard."""

    @pytest.mark.parametrize(
        "needle",
        [
            pytest.param("## Development", id="has_development_section"),
            pytest.param("## License", id="has_license_section"),
            pytest.param("axm-audit.json", id="readme_has_axm_audit_badge"),
        ],
    )
    def test_contains(self, needle: str) -> None:
        assert needle in README


class TestMemberCopierVariables:
    """copier.yml must define all variables used by doc templates."""

    @pytest.mark.parametrize(
        "needle",
        [
            pytest.param("member_name:", id="has_member_name"),
            pytest.param("module_name:", id="has_module_name"),
            pytest.param("workspace_name:", id="has_workspace_name"),
            pytest.param("org:", id="has_org"),
            pytest.param("description:", id="has_description"),
        ],
    )
    def test_contains(self, needle: str) -> None:
        assert needle in COPIER_YML
