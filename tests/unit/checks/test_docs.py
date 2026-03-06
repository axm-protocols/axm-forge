"""Tests for checks.docs — documentation checks."""

from __future__ import annotations

from pathlib import Path

from axm_init.checks.docs import (
    check_diataxis_nav,
    check_docs_gen_ref_pages,
    check_docs_plugins,
    check_mkdocs_exists,
    check_readme,
    check_readme_badges,
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


class TestCheckReadmeBadges:
    """Tests for check_readme_badges (AC4)."""

    def test_badges_present(self, tmp_path: Path) -> None:
        """README with both axm-audit and axm-init badges passes."""
        (tmp_path / "README.md").write_text(
            "# My Project\n"
            "![axm-audit](https://img.shields.io/endpoint?url=...axm-audit.json)\n"
            "![axm-init](https://img.shields.io/endpoint?url=...axm-init.json)\n"
        )
        r = check_readme_badges(tmp_path)
        assert r.passed is True
        assert r.weight == 2

    def test_badges_missing(self, tmp_path: Path) -> None:
        """README without badge strings fails."""
        (tmp_path / "README.md").write_text("# My Project\n\nNo badges here.\n")
        r = check_readme_badges(tmp_path)
        assert r.passed is False
        assert "2 badge(s)" in r.message

    def test_partial_badges(self, tmp_path: Path) -> None:
        """README with only one badge fails."""
        (tmp_path / "README.md").write_text(
            "# My Project\n"
            "![axm-audit](https://img.shields.io/endpoint?url=...axm-audit.json)\n"
        )
        r = check_readme_badges(tmp_path)
        assert r.passed is False
        assert "1 badge(s)" in r.message
        assert "axm-init" in r.details[0]

    def test_no_readme(self, empty_project: Path) -> None:
        """No README.md fails."""
        r = check_readme_badges(empty_project)
        assert r.passed is False
        assert "not found" in r.message
