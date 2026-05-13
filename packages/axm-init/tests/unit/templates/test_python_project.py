"""Unit tests for gold-standard template (pure structure assertions, no I/O)."""

from __future__ import annotations

from pathlib import Path

# Template root = src/axm_init/templates/python-project/{package_name}/
TEMPLATE_ROOT = (
    Path(__file__).resolve().parents[3]
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

    def test_has_project_urls(self) -> None:
        assert "[project.urls]" in PYPROJECT

    def test_has_homepage(self) -> None:
        assert "Homepage" in PYPROJECT

    def test_has_documentation(self) -> None:
        assert "Documentation" in PYPROJECT

    def test_has_repository(self) -> None:
        assert "Repository" in PYPROJECT

    def test_has_issues(self) -> None:
        assert "Issues" in PYPROJECT


class TestTemplatePyprojectMypy:
    """MyPy must have gold-standard settings."""

    def test_strict(self) -> None:
        assert "strict = true" in PYPROJECT

    def test_pretty(self) -> None:
        assert "pretty = true" in PYPROJECT

    def test_disallow_incomplete_defs(self) -> None:
        assert "disallow_incomplete_defs = true" in PYPROJECT

    def test_check_untyped_defs(self) -> None:
        assert "check_untyped_defs = true" in PYPROJECT


class TestTemplatePyprojectRuff:
    """Ruff must have gold-standard rule set and per-file-ignores."""

    def test_per_file_ignores_for_tests(self) -> None:
        assert "[tool.ruff.lint.per-file-ignores]" in PYPROJECT
        assert '"tests/*"' in PYPROJECT

    def test_known_first_party(self) -> None:
        assert "known-first-party" in PYPROJECT


class TestTemplatePyprojectPytest:
    """Pytest must have gold-standard options."""

    def test_strict_markers(self) -> None:
        assert '"--strict-markers"' in PYPROJECT

    def test_strict_config(self) -> None:
        assert '"--strict-config"' in PYPROJECT

    def test_import_mode_importlib(self) -> None:
        assert '"--import-mode=importlib"' in PYPROJECT

    def test_pythonpath(self) -> None:
        assert 'pythonpath = ["src"]' in PYPROJECT

    def test_filterwarnings(self) -> None:
        assert "filterwarnings" in PYPROJECT

    def test_cov_report_html(self) -> None:
        assert "html" in PYPROJECT and "cov-report" in PYPROJECT


class TestTemplatePyprojectCoverage:
    """Coverage must have gold-standard settings."""

    def test_branch(self) -> None:
        assert "branch = true" in PYPROJECT

    def test_relative_files(self) -> None:
        assert "relative_files = true" in PYPROJECT

    def test_xml_output(self) -> None:
        assert "[tool.coverage.xml]" in PYPROJECT

    def test_exclude_lines(self) -> None:
        assert "exclude_lines" in PYPROJECT


class TestTemplatePyprojectDocs:
    """Docs deps must include gen-files and literate-nav."""

    def test_mkdocs_material(self) -> None:
        assert "mkdocs-material" in PYPROJECT

    def test_mkdocstrings(self) -> None:
        assert "mkdocstrings" in PYPROJECT

    def test_gen_files(self) -> None:
        assert "mkdocs-gen-files" in PYPROJECT

    def test_literate_nav(self) -> None:
        assert "mkdocs-literate-nav" in PYPROJECT


class TestTemplateMkdocsDiataxis:
    """mkdocs.yml must have Diátaxis nav structure."""

    def test_tutorials_section(self) -> None:
        assert "Tutorials:" in MKDOCS

    def test_howto_section(self) -> None:
        assert "How-To" in MKDOCS

    def test_reference_section(self) -> None:
        assert "Reference:" in MKDOCS

    def test_explanation_section(self) -> None:
        assert "Explanation:" in MKDOCS


class TestTemplateMkdocsPlugins:
    """mkdocs.yml must have gold-standard plugins."""

    def test_gen_files_plugin(self) -> None:
        assert "gen-files" in MKDOCS

    def test_literate_nav_plugin(self) -> None:
        assert "literate-nav" in MKDOCS

    def test_mkdocstrings_plugin(self) -> None:
        assert "mkdocstrings" in MKDOCS


class TestTemplateMkdocsExtensions:
    """mkdocs.yml must have gold-standard extensions."""

    def test_mermaid_fence(self) -> None:
        assert "mermaid" in MKDOCS

    def test_tables(self) -> None:
        assert "tables" in MKDOCS

    def test_admonition(self) -> None:
        assert "admonition" in MKDOCS

    def test_superfences(self) -> None:
        assert "superfences" in MKDOCS


class TestTemplateReadme:
    """README.md must follow axm-bib standard."""

    def test_has_bold_tagline(self) -> None:
        """Bold description tagline like axm-bib."""
        assert "**{{ description }}**" in README

    def test_has_features_section(self) -> None:
        assert "## Features" in README

    def test_has_installation_section(self) -> None:
        assert "## Installation" in README

    def test_has_quick_start_section(self) -> None:
        assert "## Quick Start" in README

    def test_has_development_section(self) -> None:
        assert "## Development" in README

    def test_has_license_section(self) -> None:
        assert "## License" in README

    def test_license_uses_holder(self) -> None:
        """License references license_holder variable."""
        assert "license_holder" in README

    def test_has_separator_after_badges(self) -> None:
        """--- separator after badges like axm-bib."""
        assert "---" in README


class TestTemplatePrecommit:
    """Pre-commit must match axm-init reference."""

    def test_ruff(self) -> None:
        assert "ruff" in PRECOMMIT

    def test_mypy(self) -> None:
        assert "mypy" in PRECOMMIT

    def test_conventional_commits(self) -> None:
        assert "conventional-pre-commit" in PRECOMMIT

    def test_trailing_whitespace(self) -> None:
        assert "trailing-whitespace" in PRECOMMIT

    def test_end_of_file_fixer(self) -> None:
        assert "end-of-file-fixer" in PRECOMMIT

    def test_check_yaml(self) -> None:
        assert "check-yaml" in PRECOMMIT

    def test_check_large_files(self) -> None:
        assert "check-added-large-files" in PRECOMMIT


class TestTemplateMakefile:
    """Makefile must be aligned with axm-bib."""

    def test_has_coverage_html_in_clean(self) -> None:
        assert "coverage_html" in MAKEFILE

    def test_has_pycache_cleanup(self) -> None:
        assert "__pycache__" in MAKEFILE


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
