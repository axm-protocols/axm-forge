"""Split from ``test_ci_workflow_required_jobs.py``."""

from pathlib import Path

import pytest

from axm_init.checks.ci import check_ci_workflow_exists


class TestCheckCiWorkflowExists:
    @pytest.mark.parametrize(
        ("fixture_name", "expected"),
        [
            pytest.param("gold_project", True, id="pass"),
            pytest.param("empty_project", False, id="fail"),
        ],
    )
    def test_passed(
        self, request: pytest.FixtureRequest, fixture_name: str, expected: bool
    ) -> None:
        project: Path = request.getfixturevalue(fixture_name)
        r = check_ci_workflow_exists(project)
        assert r.passed is expected
