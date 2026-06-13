"""Split from ``test_ci_workflow_required_jobs.py``."""

import pytest

from axm_init.checks.ci import check_ci_lint_job


class TestCheckCiLintJob:
    @pytest.mark.parametrize(
        ("fixture_name", "expected"),
        [
            pytest.param("gold_project", True, id="pass"),
            pytest.param("empty_project", False, id="fail_no_ci"),
        ],
    )
    def test_passed(
        self,
        request: pytest.FixtureRequest,
        fixture_name: str,
        expected: bool,
    ) -> None:
        project = request.getfixturevalue(fixture_name)
        r = check_ci_lint_job(project)
        assert r.passed is expected
