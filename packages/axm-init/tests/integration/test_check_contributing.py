"""Split from ``test_src_layout_and_repo_files.py``."""

from pathlib import Path

from axm_init.checks.structure import check_contributing


class TestCheckContributing:
    def test_pass(self, gold_project: Path) -> None:
        r = check_contributing(gold_project)
        assert r.passed is True

    def test_fail(self, empty_project: Path) -> None:
        r = check_contributing(empty_project)
        assert r.passed is False
