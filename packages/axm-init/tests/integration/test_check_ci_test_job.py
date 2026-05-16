"""Split from ``test_ci_workflow_required_jobs.py``."""

from pathlib import Path

from axm_init.checks.ci import check_ci_test_job


class TestCheckCiTestJob:
    def test_pass(self, gold_project: Path) -> None:
        r = check_ci_test_job(gold_project)
        assert r.passed is True

    def test_fail_no_ci(self, empty_project: Path) -> None:
        r = check_ci_test_job(empty_project)
        assert r.passed is False
