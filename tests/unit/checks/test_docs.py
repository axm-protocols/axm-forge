"""Tests for checks.docs — documentation checks."""

from __future__ import annotations

from pathlib import Path

from axm_init.checks.docs import (
    check_diataxis_nav,
    check_docs_gen_ref_pages,
    check_docs_plugins,
    check_mkdocs_exists,
    check_readme,
)


class TestCheckMkdocsExists:
    def test_pass(self, gold_project: Path) -> None:
        r = check_mkdocs_exists(gold_project)
        assert r.passed is True

    def test_fail(self, empty_project: Path) -> None:
        r = check_mkdocs_exists(empty_project)
        assert r.passed is False


class TestCheckDiataxisNav:
    def test_pass(self, gold_project: Path) -> None:
        r = check_diataxis_nav(gold_project)
        assert r.passed is True

    def test_fail_flat_nav(self, tmp_path: Path) -> None:
        (tmp_path / "mkdocs.yml").write_text("nav:\n  - Home: index.md\n")
        r = check_diataxis_nav(tmp_path)
        assert r.passed is False

    def test_fail_partial(self, tmp_path: Path) -> None:
        mkdocs = "nav:\n  - Tutorials:\n    - t.md\n  - Reference:\n    - r.md\n"
        (tmp_path / "mkdocs.yml").write_text(mkdocs)
        r = check_diataxis_nav(tmp_path)
        assert r.passed is False
        # Should report which Diátaxis sections are missing


class TestCheckDocsPlugins:
    def test_pass(self, gold_project: Path) -> None:
        r = check_docs_plugins(gold_project)
        assert r.passed is True

    def test_fail_no_plugins(self, tmp_path: Path) -> None:
        (tmp_path / "mkdocs.yml").write_text("site_name: x\n")
        r = check_docs_plugins(tmp_path)
        assert r.passed is False


class TestCheckDocsGenRefPages:
    def test_pass(self, gold_project: Path) -> None:
        r = check_docs_gen_ref_pages(gold_project)
        assert r.passed is True

    def test_fail(self, empty_project: Path) -> None:
        r = check_docs_gen_ref_pages(empty_project)
        assert r.passed is False


class TestCheckReadme:
    def test_pass(self, gold_project: Path) -> None:
        r = check_readme(gold_project)
        assert r.passed is True

    def test_fail_missing(self, empty_project: Path) -> None:
        r = check_readme(empty_project)
        assert r.passed is False

    def test_fail_no_features(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# test\n## Installation\n")
        r = check_readme(tmp_path)
        assert r.passed is False
