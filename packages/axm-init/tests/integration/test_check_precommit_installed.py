"""Split from ``test_precommit_and_makefile_tooling.py``."""

from pathlib import Path

import pytest

from axm_init.checks.tooling import check_precommit_installed


class TestCheckPrecommitInstalled:
    def test_pass_hooks_installed(self, gold_project: Path) -> None:
        """Config exists + .git/hooks/pre-commit exists -> PASS."""
        r = check_precommit_installed(gold_project)
        assert r.passed is True
        assert r.weight == 2

    def test_pass_no_config(self, empty_project: Path) -> None:
        """No .pre-commit-config.yaml -> PASS (nothing to install)."""
        r = check_precommit_installed(empty_project)
        assert r.passed is True

    def test_fail_config_no_hooks(self, tmp_path: Path) -> None:
        """Config exists but no .git/hooks/pre-commit -> FAIL."""
        (tmp_path / ".pre-commit-config.yaml").write_text("repos:\n")
        r = check_precommit_installed(tmp_path)
        assert r.passed is False
        assert "pre-commit install" in r.fix

    @pytest.mark.parametrize(
        "create_git_dir",
        [
            pytest.param(True, id="git_dir_no_hooks"),
            pytest.param(False, id="no_git_dir"),
        ],
    )
    def test_fail_when_hooks_missing(
        self, tmp_path: Path, create_git_dir: bool
    ) -> None:
        """Config exists but hooks not installed -> FAIL."""
        (tmp_path / ".pre-commit-config.yaml").write_text("repos:\n")
        if create_git_dir:
            (tmp_path / ".git").mkdir()
        r = check_precommit_installed(tmp_path)
        assert r.passed is False
