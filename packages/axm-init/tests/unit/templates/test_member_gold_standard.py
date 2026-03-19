"""Unit tests for workspace-member Copier template — gold standard compliance.

These tests read the raw Jinja template files and verify they contain
the expected Diátaxis configurations and monorepo compatibility constraints.
"""

from __future__ import annotations

from pathlib import Path

# Template root = src/axm_init/templates/workspace-member/
TEMPLATE_ROOT = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "axm_init"
    / "templates"
    / "workspace-member"
)

COPIER_YML = (TEMPLATE_ROOT / "copier.yml").read_text()
MKDOCS = (TEMPLATE_ROOT / "mkdocs.yml.jinja").read_text()
README = (TEMPLATE_ROOT / "README.md.jinja").read_text()

DOCS_DIR = TEMPLATE_ROOT / "docs"
DOCS_INDEX = (DOCS_DIR / "index.md.jinja").read_text()


# ─────────────────────────────────────────────────────────────────────────────
# Docs Diátaxis structure tests
# ─────────────────────────────────────────────────────────────────────────────


class TestMemberDocsStructure:
    """Docs must have Diátaxis directory structure."""

    def test_no_flat_getting_started(self) -> None:
        """Old flat getting-started.md should NOT exist."""
        assert not (DOCS_DIR / "getting-started.md.jinja").exists()

    def test_tutorials_dir_exists(self) -> None:
        assert (DOCS_DIR / "tutorials").is_dir()

    def test_tutorials_getting_started_exists(self) -> None:
        assert (DOCS_DIR / "tutorials" / "getting-started.md.jinja").exists()

    def test_howto_dir_exists(self) -> None:
        assert (DOCS_DIR / "howto").is_dir()

    def test_howto_index_exists(self) -> None:
        assert (DOCS_DIR / "howto" / "index.md").exists()

    def test_reference_dir_exists(self) -> None:
        assert (DOCS_DIR / "reference").is_dir()

    def test_reference_cli_exists(self) -> None:
        assert (DOCS_DIR / "reference" / "cli.md.jinja").exists()

    def test_explanation_dir_exists(self) -> None:
        assert (DOCS_DIR / "explanation").is_dir()

    def test_explanation_architecture_exists(self) -> None:
        assert (DOCS_DIR / "explanation" / "architecture.md.jinja").exists()

    def test_no_gen_ref_pages(self) -> None:
        """gen_ref_pages is dead code in nav-only members.

        Standalone python-project members handle this themselves.
        """
        assert not (DOCS_DIR / "gen_ref_pages.py.jinja").exists()


# ─────────────────────────────────────────────────────────────────────────────
# mkdocs.yml.jinja tests
# ─────────────────────────────────────────────────────────────────────────────


class TestMemberMkdocsDiataxis:
    """mkdocs.yml must have Diátaxis nav structure."""

    def test_tutorials_section(self) -> None:
        assert "Tutorials:" in MKDOCS

    def test_howto_section(self) -> None:
        assert "How-To" in MKDOCS

    def test_reference_section(self) -> None:
        assert "Reference:" in MKDOCS

    def test_explanation_section(self) -> None:
        assert "Explanation:" in MKDOCS


class TestMemberMkdocsNavOnly:
    """Workspace-member mkdocs.yml must NOT have plugins — parent handles them."""

    def test_no_plugins_block(self) -> None:
        """Plugins are declared in the workspace root mkdocs.yml only."""
        assert "plugins:" not in MKDOCS


class TestMemberMkdocsMonorepoCompat:
    """Workspace-member mkdocs.yml must be monorepo-compatible."""

    def test_no_theme_block(self) -> None:
        """Theme is inherited from workspace root — no local theme block."""
        assert "theme:" not in MKDOCS

    def test_no_site_url(self) -> None:
        """site_url is set at workspace root level."""
        assert "site_url:" not in MKDOCS

    def test_no_repo_url(self) -> None:
        """repo_url is set at workspace root level."""
        assert "repo_url:" not in MKDOCS


# ─────────────────────────────────────────────────────────────────────────────
# docs/index.md.jinja tests
# ─────────────────────────────────────────────────────────────────────────────


class TestMemberDocsIndex:
    """docs/index.md must follow workspace-member standard."""

    def test_has_member_name_heading(self) -> None:
        assert "{{ member_name }}" in DOCS_INDEX

    def test_has_description(self) -> None:
        assert "{{ description }}" in DOCS_INDEX

    def test_has_install_section(self) -> None:
        assert "## Installation" in DOCS_INDEX

    def test_has_quick_start(self) -> None:
        assert "## Quick Start" in DOCS_INDEX

    def test_has_features(self) -> None:
        assert "## Features" in DOCS_INDEX

    def test_has_cta_buttons(self) -> None:
        assert "Get Started" in DOCS_INDEX
        assert "Reference" in DOCS_INDEX

    def test_has_axm_init_badge(self) -> None:
        assert "axm-init.json" in DOCS_INDEX

    def test_has_axm_audit_badge(self) -> None:
        assert "axm-audit.json" in DOCS_INDEX

    def test_uses_workspace_badge_paths(self) -> None:
        """Badge URLs must use workspace_name/member_name path pattern."""
        assert "{{ workspace_name }}" in DOCS_INDEX
        assert "{{ member_name }}/axm-init.json" in DOCS_INDEX


# ─────────────────────────────────────────────────────────────────────────────
# README.md.jinja tests
# ─────────────────────────────────────────────────────────────────────────────


class TestMemberReadme:
    """README.md must follow workspace-member standard."""

    def test_has_development_section(self) -> None:
        assert "## Development" in README

    def test_has_license_section(self) -> None:
        assert "## License" in README

    def test_readme_has_axm_audit_badge(self) -> None:
        """README must link to the axm-audit.json endpoint badge."""
        assert "axm-audit.json" in README


# ─────────────────────────────────────────────────────────────────────────────
# copier.yml variable tests
# ─────────────────────────────────────────────────────────────────────────────


class TestMemberCopierVariables:
    """copier.yml must define all variables used by doc templates."""

    def test_has_member_name(self) -> None:
        assert "member_name:" in COPIER_YML

    def test_has_module_name(self) -> None:
        assert "module_name:" in COPIER_YML

    def test_has_workspace_name(self) -> None:
        assert "workspace_name:" in COPIER_YML

    def test_has_org(self) -> None:
        assert "org:" in COPIER_YML

    def test_has_description(self) -> None:
        assert "description:" in COPIER_YML
