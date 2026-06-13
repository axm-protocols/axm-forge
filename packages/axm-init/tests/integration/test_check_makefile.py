"""Split from ``test_precommit_and_makefile_tooling.py``."""

from pathlib import Path

import pytest

from axm_init.checks.tooling import check_makefile


class TestCheckMakefile:
    @pytest.mark.parametrize(
        ("fixture_name", "expected"),
        [
            pytest.param("gold_project", True, id="pass"),
            pytest.param("empty_project", False, id="fail_missing"),
        ],
    )
    def test_passed(
        self, request: pytest.FixtureRequest, fixture_name: str, expected: bool
    ) -> None:
        project: Path = request.getfixturevalue(fixture_name)
        r = check_makefile(project)
        assert r.passed is expected

    def test_fail_partial_targets(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("install:\n\techo hi\n")
        r = check_makefile(tmp_path)
        assert r.passed is False
        assert len(r.details) > 0  # reports missing targets
