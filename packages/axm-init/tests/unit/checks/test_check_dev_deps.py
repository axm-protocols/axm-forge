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

    def test_prek_satisfies_dev_group(self, tmp_path: Path) -> None:
        """AC1: dev group pinning prek (no pre-commit) passes clean.

        prek is the gold-standard runner: the check passes and carries no
        migration warning in its details.
        """
        toml = (
            '[project]\nname="x"\n[dependency-groups]\n'
            'dev = ["pytest", "ruff", "mypy", "prek>=0.4,<0.5"]\n'
        )
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_dev_deps(tmp_path)
        assert r.passed is True
        assert not any("migrat" in d.lower() for d in r.details)

    def test_pre_commit_only_passes_with_warning(self, tmp_path: Path) -> None:
        """AC2: dev group with pre-commit (no prek) passes with soft warning.

        A project still pinning the legacy pre-commit runner is tolerated:
        the check stays green (does not dent the score) but surfaces a soft
        deprecation note inviting migration to prek.
        """
        toml = (
            '[project]\nname="x"\n[dependency-groups]\n'
            'dev = ["pytest", "ruff", "mypy", "pre-commit>=4.0"]\n'
        )
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_dev_deps(tmp_path)
        assert r.passed is True
        assert any("migrat" in d.lower() for d in r.details)

    def test_no_runner_fails(self, tmp_path: Path) -> None:
        """AC3: dev group with neither prek nor pre-commit fails.

        With no hook runner at all the check fails and the message names the
        missing runner.
        """
        toml = (
            '[project]\nname="x"\n[dependency-groups]\n'
            'dev = ["pytest", "ruff", "mypy"]\n'
        )
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_dev_deps(tmp_path)
        assert r.passed is False
        assert "prek" in r.details[0]


@pytest.fixture
def missing_deps_project(tmp_path: Path) -> Path:
    toml = '[project]\nname="x"\n[dependency-groups]\ndev = ["pytest"]\n'
    (tmp_path / "pyproject.toml").write_text(toml)
    return tmp_path
