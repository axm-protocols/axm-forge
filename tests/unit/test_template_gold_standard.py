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
    / "{{package_name}}"
)

PYPROJECT = (TEMPLATE_ROOT / "pyproject.toml.jinja").read_text()
MKDOCS = (TEMPLATE_ROOT / "mkdocs.yml.jinja").read_text()


# ─────────────────────────────────────────────────────────────────────────────
# pyproject.toml.jinja tests
# ─────────────────────────────────────────────────────────────────────────────


class TestTemplatePyprojectVersion:
    """Version configuration must use hatch-vcs."""

    def test_dynamic_version(self) -> None:
        """dynamic = ["version"] must be present."""
        assert 'dynamic = ["version"]' in PYPROJECT

    def test_hatch_vcs_in_build_requires(self) -> None:
        """hatch-vcs must be in build-system.requires."""
        assert '"hatch-vcs"' in PYPROJECT


class TestTemplatePyprojectUrls:
    """[project.urls] must be present with 4 URLs."""

    def test_has_project_urls(self) -> None:
        """[project.urls] section must exist."""
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
        """per-file-ignores must include tests/* with S101."""
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
        """coverage.xml output must be configured."""
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


# ─────────────────────────────────────────────────────────────────────────────
# mkdocs.yml.jinja tests
# ─────────────────────────────────────────────────────────────────────────────


class TestTemplateMkdocsDiataxis:
    """mkdocs.yml must have Diátaxis nav structure."""

    def test_tutorials_section(self) -> None:
        assert "Tutorials:" in MKDOCS or "tutorials:" in MKDOCS.lower()

    def test_howto_section(self) -> None:
        assert "How-To" in MKDOCS or "howto" in MKDOCS.lower()

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
