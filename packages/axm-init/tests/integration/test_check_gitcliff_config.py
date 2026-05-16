"""Split from ``test_changelog_gitcliff_requirement.py``."""

from pathlib import Path

from axm_init.checks.changelog import check_gitcliff_config


class TestCheckGitcliffConfig:
    def test_pass(self, gold_project: Path) -> None:
        r = check_gitcliff_config(gold_project)
        assert r.passed is True

    def test_fail(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\n')
        r = check_gitcliff_config(tmp_path)
        assert r.passed is False
