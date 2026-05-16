"""Split from ``test_ci_workflow_required_jobs.py``."""

from pathlib import Path

from axm_init.checks.ci import check_ci_workflow_exists


class TestCheckCiWorkflowExists:
    def test_pass(self, gold_project: Path) -> None:
        r = check_ci_workflow_exists(gold_project)
        assert r.passed is True

    def test_fail(self, empty_project: Path) -> None:
        r = check_ci_workflow_exists(empty_project)
        assert r.passed is False
