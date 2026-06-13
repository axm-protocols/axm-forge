"""Split from ``test_changelog_gitcliff_requirement.py``."""

from pathlib import Path

import pytest

from axm_init.checks.changelog import check_gitcliff_config


@pytest.fixture()
def bare_pyproject(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\n')
    return tmp_path


class TestCheckGitcliffConfig:
    @pytest.mark.parametrize(
        ("fixture_name", "expected"),
        [
            pytest.param("gold_project", True, id="pass"),
            pytest.param("bare_pyproject", False, id="fail"),
        ],
    )
    def test_passed(
        self, request: pytest.FixtureRequest, fixture_name: str, expected: bool
    ) -> None:
        project: Path = request.getfixturevalue(fixture_name)
        r = check_gitcliff_config(project)
        assert r.passed is expected
