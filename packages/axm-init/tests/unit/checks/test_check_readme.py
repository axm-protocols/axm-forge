"""Split from ``test_diataxis_docs_layout_requirements.py``."""

from pathlib import Path

import pytest

from axm_init.checks.docs import check_readme


class TestCheckReadme:
    @pytest.mark.parametrize(
        ("fixture_name", "expected"),
        [
            pytest.param("gold_project", True, id="pass"),
            pytest.param("empty_project", False, id="fail_missing"),
            pytest.param("no_features_project", False, id="fail_no_features"),
        ],
    )
    def test_passed(
        self,
        request: pytest.FixtureRequest,
        fixture_name: str,
        expected: bool,
    ) -> None:
        project = request.getfixturevalue(fixture_name)
        r = check_readme(project)
        assert r.passed is expected


@pytest.fixture
def no_features_project(tmp_path: Path) -> Path:
    (tmp_path / "README.md").write_text("# test\n## Installation\n")
    return tmp_path
