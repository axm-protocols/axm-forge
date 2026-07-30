"""Split from ``test_precommit_and_makefile_tooling.py``."""

from pathlib import Path

import pytest

from axm_init.checks.tooling import check_precommit_basic


class TestCheckPrecommitBasic:
    @pytest.mark.parametrize(
        ("project_fixture", "expected"),
        [
            pytest.param("gold_project", True, id="pass-gold"),
            pytest.param("empty_project", False, id="fail-no-file"),
        ],
    )
    def test_passed(
        self,
        project_fixture: str,
        expected: bool,
        request: pytest.FixtureRequest,
    ) -> None:
        project: Path = request.getfixturevalue(project_fixture)
        r = check_precommit_basic(project)
        assert r.passed is expected
