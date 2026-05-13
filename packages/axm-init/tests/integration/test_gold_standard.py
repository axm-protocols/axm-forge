"""Unit tests for Copier template — gold standard compliance.

These tests read the raw Jinja template files and verify they contain
the expected gold-standard configurations, based on the axm-bib reference.
"""

from __future__ import annotations

from pathlib import Path

import pytest

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

    @pytest.mark.parametrize(
        "expected",
        [
            pytest.param("uvx axm-init check", id="check_step"),
            pytest.param("peaceiris/actions-gh-pages", id="badge_push"),
            pytest.param("axm-protocols/axm-init", id="fetches_logo"),
        ],
    )
    def test_axm_workflow_contains(self, expected: str) -> None:
        """Workflow must contain expected literal."""
        wf = (
            TEMPLATE_ROOT / ".github" / "workflows" / "axm-quality.yml.jinja"
        ).read_text()
        assert expected in wf


class TestTemplateAxmAuditWorkflow:
    """Template must include axm-audit steps in axm-quality workflow."""

    def test_axm_audit_workflow_exists(self) -> None:
        """axm-quality.yml.jinja must exist in .github/workflows/."""
        assert (
            TEMPLATE_ROOT / ".github" / "workflows" / "axm-quality.yml.jinja"
        ).exists()

    @pytest.mark.parametrize(
        "expected",
        [
            pytest.param("uvx axm-audit audit", id="audit_step"),
            pytest.param("peaceiris/actions-gh-pages", id="badge_push"),
            pytest.param("axm-protocols/axm-audit", id="fetches_logo"),
        ],
    )
    def test_axm_audit_workflow_contains(self, expected: str) -> None:
        """Workflow must contain expected literal."""
        wf = (
            TEMPLATE_ROOT / ".github" / "workflows" / "axm-quality.yml.jinja"
        ).read_text()
        assert expected in wf
