"""Tests for checks.changelog — gitcliff and manual changelog checks."""

from __future__ import annotations

from pathlib import Path

from axm_init.checks.changelog import check_gitcliff_config, check_no_manual_changelog


class TestCheckGitcliffConfig:
    def test_pass(self, gold_project: Path) -> None:
        r = check_gitcliff_config(gold_project)
        assert r.passed is True

    def test_fail(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\n')
        r = check_gitcliff_config(tmp_path)
        assert r.passed is False


class TestCheckNoManualChangelog:
    def test_pass(self, gold_project: Path) -> None:
        r = check_no_manual_changelog(gold_project)
        assert r.passed is True

    def test_fail_has_changelog(self, tmp_path: Path) -> None:
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n")
        r = check_no_manual_changelog(tmp_path)
        assert r.passed is False
