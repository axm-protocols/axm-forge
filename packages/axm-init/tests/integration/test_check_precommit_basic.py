"""Split from ``test_precommit_and_makefile_tooling.py``."""

from pathlib import Path

from axm_init.checks.tooling import check_precommit_basic


class TestCheckPrecommitBasic:
    def test_pass(self, gold_project: Path) -> None:
        r = check_precommit_basic(gold_project)
        assert r.passed is True

    def test_fail_no_file(self, empty_project: Path) -> None:
        r = check_precommit_basic(empty_project)
        assert r.passed is False
