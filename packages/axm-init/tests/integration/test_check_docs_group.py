"""Tests for checks.deps — dependency hygiene checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.checks.deps import check_docs_group


@pytest.fixture()
def docs_group_missing(tmp_path: Path) -> Path:
    toml = '[project]\nname="x"\n[dependency-groups]\ndocs = ["mkdocs"]\n'
    (tmp_path / "pyproject.toml").write_text(toml)
    return tmp_path


class TestCheckDocsDeps:
    @pytest.mark.parametrize(
        ("fixture_name", "expected"),
        [
            pytest.param("gold_project", True, id="pass"),
            pytest.param("docs_group_missing", False, id="fail_missing"),
        ],
    )
    def test_passed(
        self, request: pytest.FixtureRequest, fixture_name: str, expected: bool
    ) -> None:
        project: Path = request.getfixturevalue(fixture_name)
        r = check_docs_group(project)
        assert r.passed is expected
