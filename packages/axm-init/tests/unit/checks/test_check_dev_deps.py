"""Split from ``test_dependency_hygiene_dev_and_docs.py``."""

from pathlib import Path

import pytest

from axm_init.checks.deps import check_dev_deps


class TestCheckDevDeps:
    @pytest.mark.parametrize(
        ("fixture_name", "expected"),
        [
            pytest.param("gold_project", True, id="pass"),
            pytest.param("empty_project", False, id="fail_no_pyproject"),
            pytest.param("missing_deps_project", False, id="fail_missing_deps"),
        ],
    )
    def test_passed(
        self,
        request: pytest.FixtureRequest,
        fixture_name: str,
        expected: bool,
    ) -> None:
        project = request.getfixturevalue(fixture_name)
        r = check_dev_deps(project)
        assert r.passed is expected


@pytest.fixture
def missing_deps_project(tmp_path: Path) -> Path:
    toml = '[project]\nname="x"\n[dependency-groups]\ndev = ["pytest"]\n'
    (tmp_path / "pyproject.toml").write_text(toml)
    return tmp_path
