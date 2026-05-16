"""Split from ``test_precommit_and_makefile_tooling.py``."""

from pathlib import Path

from axm_init.checks.tooling import check_precommit_conventional


class TestCheckPrecommitConventional:
    def test_pass(self, gold_project: Path) -> None:
        r = check_precommit_conventional(gold_project)
        assert r.passed is True

    def test_fail_no_hook(self, tmp_path: Path) -> None:
        (tmp_path / ".pre-commit-config.yaml").write_text("repos:\n  - repo: x\n")
        r = check_precommit_conventional(tmp_path)
        assert r.passed is False
