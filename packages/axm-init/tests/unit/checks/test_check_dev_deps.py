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

    def test_pre_commit_alone_fails(self, tmp_path: Path) -> None:
        """AC1: dev group with pre-commit but no prek is now flagged.

        The gold standard migrated to prek; a project still pinning the old
        pre-commit package (and missing prek) must fail the dev-deps check.
        """
        toml = (
            '[project]\nname="x"\n[dependency-groups]\n'
            'dev = ["pytest", "ruff", "mypy", "pre-commit>=4.0"]\n'
        )
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_dev_deps(tmp_path)
        assert r.passed is False
        assert "prek" in r.details[0]

    def test_prek_satisfies_dev_group(self, tmp_path: Path) -> None:
        """AC1: dev group pinning prek (no pre-commit) passes the check."""
        toml = (
            '[project]\nname="x"\n[dependency-groups]\n'
            'dev = ["pytest", "ruff", "mypy", "prek>=0.4,<0.5"]\n'
        )
        (tmp_path / "pyproject.toml").write_text(toml)
        assert check_dev_deps(tmp_path).passed is True


@pytest.fixture
def missing_deps_project(tmp_path: Path) -> Path:
    toml = '[project]\nname="x"\n[dependency-groups]\ndev = ["pytest"]\n'
    (tmp_path / "pyproject.toml").write_text(toml)
    return tmp_path
