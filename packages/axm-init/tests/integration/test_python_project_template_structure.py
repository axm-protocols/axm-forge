"""Unit tests for gold-standard template (pure structure assertions, no I/O)."""

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

COPIER_YML = (TEMPLATE_ROOT / "copier.yml").read_text()
PYPROJECT = (TEMPLATE_ROOT / "pyproject.toml.jinja").read_text()
MKDOCS = (TEMPLATE_ROOT / "mkdocs.yml.jinja").read_text()
README = (TEMPLATE_ROOT / "README.md.jinja").read_text()
PRECOMMIT = (TEMPLATE_ROOT / ".pre-commit-config.yaml").read_text()
MAKEFILE = (TEMPLATE_ROOT / "Makefile").read_text()

DOCS_DIR = TEMPLATE_ROOT / "docs"


# ──────────────────────────────────────────────────────────────────────
# AXM check badge & workflow tests
# ──────────────────────────────────────────────────────────────────────

DOCS_INDEX = (DOCS_DIR / "index.md.jinja").read_text()


class TestCopierQuestions:
    """Verify copier.yml question ordering and content."""

    def test_has_license_holder(self) -> None:
        """license_holder question must exist."""
        assert "license_holder:" in COPIER_YML

    def test_org_is_open_text(self) -> None:
        """org must NOT have choices (open text field)."""
        # Find the org section and check there are no choices under it
        lines = COPIER_YML.split("\n")
        in_org = False
        for line in lines:
            if line.startswith("org:"):
                in_org = True
                continue
            if in_org:
                if line.startswith("  "):
                    assert "choices:" not in line, "org should not have choices"
                else:
                    break

    def test_license_before_org(self) -> None:
        """license question must appear before org question."""
        assert COPIER_YML.index("license:") < COPIER_YML.index("org:")

    def test_license_holder_after_license(self) -> None:
        """license_holder must appear after license."""
        assert COPIER_YML.index("license:") < COPIER_YML.index("license_holder:")

    def test_license_holder_before_org(self) -> None:
        """license_holder must appear before org."""
        assert COPIER_YML.index("license_holder:") < COPIER_YML.index("org:")


class TestTemplatePyprojectVersion:
    """Version configuration must use hatch-vcs."""

    def test_dynamic_version(self) -> None:
        assert 'dynamic = ["version"]' in PYPROJECT

    def test_hatch_vcs_in_build_requires(self) -> None:
        assert '"hatch-vcs"' in PYPROJECT


class TestTemplatePyprojectUrls:
    """[project.urls] must be present with 4 URLs."""

    @pytest.mark.parametrize(
        "needle",
        [
            pytest.param("[project.urls]", id="has_project_urls"),
            pytest.param("Homepage", id="has_homepage"),
            pytest.param("Documentation", id="has_documentation"),
            pytest.param("Repository", id="has_repository"),
            pytest.param("Issues", id="has_issues"),
        ],
    )
    def test_contains(self, needle: str) -> None:
        assert needle in PYPROJECT


class TestTemplatePyprojectMypy:
    """MyPy must have gold-standard settings."""

    @pytest.mark.parametrize(
        "needle",
        [
            pytest.param("strict = true", id="strict"),
            pytest.param("pretty = true", id="pretty"),
            pytest.param(
                "disallow_incomplete_defs = true", id="disallow_incomplete_defs"
            ),
            pytest.param("check_untyped_defs = true", id="check_untyped_defs"),
        ],
    )
    def test_contains(self, needle: str) -> None:
        assert needle in PYPROJECT


class TestTemplatePyprojectRuff:
    """Ruff must have gold-standard rule set and per-file-ignores."""

    def test_per_file_ignores_for_tests(self) -> None:
        assert "[tool.ruff.lint.per-file-ignores]" in PYPROJECT
        assert '"tests/*"' in PYPROJECT

    def test_known_first_party(self) -> None:
        assert "known-first-party" in PYPROJECT


class TestTemplatePyprojectPytest:
    """Pytest must have gold-standard options."""

    @pytest.mark.parametrize(
        "needle",
        [
            pytest.param('"--strict-markers"', id="strict_markers"),
            pytest.param('"--strict-config"', id="strict_config"),
            pytest.param('"--import-mode=importlib"', id="import_mode_importlib"),
            pytest.param('pythonpath = ["src"]', id="pythonpath"),
            pytest.param("filterwarnings", id="filterwarnings"),
        ],
    )
    def test_contains(self, needle: str) -> None:
        assert needle in PYPROJECT

    def test_cov_report_html(self) -> None:
        assert "html" in PYPROJECT and "cov-report" in PYPROJECT


class TestTemplatePyprojectCoverage:
    """Coverage must have gold-standard settings."""

    @pytest.mark.parametrize(
        "needle",
        [
            pytest.param("branch = true", id="branch"),
            pytest.param("relative_files = true", id="relative_files"),
            pytest.param("[tool.coverage.xml]", id="xml_output"),
            pytest.param("exclude_lines", id="exclude_lines"),
        ],
    )
    def test_contains(self, needle: str) -> None:
        assert needle in PYPROJECT


class TestTemplatePyprojectDocs:
    """Docs deps must include gen-files and literate-nav."""

    @pytest.mark.parametrize(
        "needle",
        [
            pytest.param("mkdocs-material", id="mkdocs_material"),
            pytest.param("mkdocstrings", id="mkdocstrings"),
            pytest.param("mkdocs-gen-files", id="gen_files"),
            pytest.param("mkdocs-literate-nav", id="literate_nav"),
        ],
    )
    def test_contains(self, needle: str) -> None:
        assert needle in PYPROJECT


class TestTemplateMkdocsDiataxis:
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


class TestTemplateMkdocsPlugins:
    """mkdocs.yml must have gold-standard plugins."""

    @pytest.mark.parametrize(
        "needle",
        [
            pytest.param("gen-files", id="gen_files_plugin"),
            pytest.param("literate-nav", id="literate_nav_plugin"),
            pytest.param("mkdocstrings", id="mkdocstrings_plugin"),
        ],
    )
    def test_contains(self, needle: str) -> None:
        assert needle in MKDOCS


class TestTemplateMkdocsExtensions:
    """mkdocs.yml must have gold-standard extensions."""

    @pytest.mark.parametrize(
        "needle",
        [
            pytest.param("mermaid", id="mermaid_fence"),
            pytest.param("tables", id="tables"),
            pytest.param("admonition", id="admonition"),
            pytest.param("superfences", id="superfences"),
        ],
    )
    def test_contains(self, needle: str) -> None:
        assert needle in MKDOCS


class TestTemplateReadme:
    """README.md must follow axm-bib standard."""

    @pytest.mark.parametrize(
        "needle",
        [
            pytest.param("**{{ description }}**", id="has_bold_tagline"),
            pytest.param("## Features", id="has_features_section"),
            pytest.param("## Installation", id="has_installation_section"),
            pytest.param("## Quick Start", id="has_quick_start_section"),
            pytest.param("## Development", id="has_development_section"),
            pytest.param("## License", id="has_license_section"),
            pytest.param("license_holder", id="license_uses_holder"),
            pytest.param("---", id="has_separator_after_badges"),
        ],
    )
    def test_contains(self, needle: str) -> None:
        assert needle in README


class TestTemplatePrecommit:
    """Pre-commit must match axm-init reference."""

    @pytest.mark.parametrize(
        "needle",
        [
            pytest.param("ruff", id="ruff"),
            pytest.param("mypy", id="mypy"),
            pytest.param("conventional-pre-commit", id="conventional_commits"),
            pytest.param("trailing-whitespace", id="trailing_whitespace"),
            pytest.param("end-of-file-fixer", id="end_of_file_fixer"),
            pytest.param("check-yaml", id="check_yaml"),
            pytest.param("check-added-large-files", id="check_large_files"),
        ],
    )
    def test_contains(self, needle: str) -> None:
        assert needle in PRECOMMIT


class TestTemplateMakefile:
    """Makefile must be aligned with axm-bib."""

    @pytest.mark.parametrize(
        "needle",
        [
            pytest.param("coverage_html", id="has_coverage_html_in_clean"),
            pytest.param("__pycache__", id="has_pycache_cleanup"),
        ],
    )
    def test_contains(self, needle: str) -> None:
        assert needle in MAKEFILE


class TestTemplateAxmBadge:
    """README and docs must include the AXM check badge."""

    def test_readme_has_axm_init_badge(self) -> None:
        """README must link to the axm-init.json endpoint badge."""
        assert "axm-init.json" in README

    def test_readme_has_axm_audit_badge(self) -> None:
        """README must link to the axm-audit.json endpoint badge."""
        assert "axm-audit.json" in README

    def test_docs_index_has_axm_init_badge(self) -> None:
        """docs/index.md must link to the axm-init.json endpoint badge."""
        assert "axm-init.json" in DOCS_INDEX

    def test_docs_index_has_axm_audit_badge(self) -> None:
        """docs/index.md must link to the axm-audit.json endpoint badge."""
        assert "axm-audit.json" in DOCS_INDEX
