"""Unit tests for Copier template — gold standard compliance.

These tests read the raw Jinja template files and verify they contain
the expected gold-standard configurations, based on the axm-bib reference.
"""

from __future__ import annotations

from pathlib import Path

# Template root = src/axm_init/templates/python-project/{package_name}/
TEMPLATE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "axm_init"
    / "templates"
    / "python-project"
)

DOCS_DIR = TEMPLATE_ROOT / "docs"


# ─────────────────────────────────────────────────────────────────────────────
# Docs Diátaxis structure tests
# ─────────────────────────────────────────────────────────────────────────────


class TestTemplateDocsStructure:
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

    def test_gen_ref_pages_exists(self) -> None:
        assert (DOCS_DIR / "gen_ref_pages.py.jinja").exists()


class TestTemplateNoChangelog:
    """CHANGELOG.md should NOT exist (git-cliff auto-generates)."""

    def test_no_changelog(self) -> None:
        assert not (TEMPLATE_ROOT / "CHANGELOG.md").exists()


class TestTemplateAxmWorkflow:
    """Template must include axm-quality workflow with axm-init check."""

    def test_axm_workflow_exists(self) -> None:
        """axm-quality.yml.jinja must exist in .github/workflows/."""
        assert (
            TEMPLATE_ROOT / ".github" / "workflows" / "axm-quality.yml.jinja"
        ).exists()

    def test_axm_workflow_has_check_step(self) -> None:
        """Workflow must run axm-init check via uvx."""
        wf = (
            TEMPLATE_ROOT / ".github" / "workflows" / "axm-quality.yml.jinja"
        ).read_text()
        assert "uvx axm-init check" in wf

    def test_axm_workflow_has_badge_push(self) -> None:
        """Workflow must push badge to gh-pages."""
        wf = (
            TEMPLATE_ROOT / ".github" / "workflows" / "axm-quality.yml.jinja"
        ).read_text()
        assert "peaceiris/actions-gh-pages" in wf

    def test_axm_workflow_fetches_logo(self) -> None:
        """Workflow must fetch logo from axm-protocols/axm-init repo."""
        wf = (
            TEMPLATE_ROOT / ".github" / "workflows" / "axm-quality.yml.jinja"
        ).read_text()
        assert "axm-protocols/axm-init" in wf


class TestTemplateAxmAuditWorkflow:
    """Template must include axm-audit steps in axm-quality workflow."""

    def test_axm_audit_workflow_exists(self) -> None:
        """axm-quality.yml.jinja must exist in .github/workflows/."""
        assert (
            TEMPLATE_ROOT / ".github" / "workflows" / "axm-quality.yml.jinja"
        ).exists()

    def test_axm_audit_workflow_has_audit_step(self) -> None:
        """Workflow must run axm-audit via uvx."""
        wf = (
            TEMPLATE_ROOT / ".github" / "workflows" / "axm-quality.yml.jinja"
        ).read_text()
        assert "uvx axm-audit audit" in wf

    def test_axm_audit_workflow_has_badge_push(self) -> None:
        """Workflow must push badge to gh-pages."""
        wf = (
            TEMPLATE_ROOT / ".github" / "workflows" / "axm-quality.yml.jinja"
        ).read_text()
        assert "peaceiris/actions-gh-pages" in wf

    def test_axm_audit_workflow_fetches_logo(self) -> None:
        """Workflow must fetch logo from axm-protocols/axm-audit repo."""
        wf = (
            TEMPLATE_ROOT / ".github" / "workflows" / "axm-quality.yml.jinja"
        ).read_text()
        assert "axm-protocols/axm-audit" in wf
