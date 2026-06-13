"""Split from ``test_src_layout_and_repo_files.py``."""

from pathlib import Path

import pytest

from axm_init.checks.structure import check_license_file


class TestCheckLicenseFile:
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
        r = check_license_file(project)
        assert r.passed is expected
