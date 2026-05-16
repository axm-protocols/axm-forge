"""Split from ``test_ci_workflow_required_jobs.py``."""

from pathlib import Path

from axm_init.checks.ci import check_dependabot


class TestCheckDependabot:
    def test_pass(self, gold_project: Path) -> None:
        r = check_dependabot(gold_project)
        assert r.passed is True
        assert r.weight == 2

    def test_fail_missing(self, empty_project: Path) -> None:
        r = check_dependabot(empty_project)
        assert r.passed is False
