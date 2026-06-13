"""Split from ``test_diataxis_docs_layout_requirements.py``."""

from pathlib import Path

import pytest

from axm_init.checks.docs import check_diataxis_nav


class TestCheckDiataxisNav:
    @pytest.mark.parametrize(
        ("fixture_name", "expected"),
        [
            pytest.param("gold_project", True, id="pass"),
            pytest.param("flat_nav_project", False, id="fail_flat_nav"),
            pytest.param("partial_nav_project", False, id="fail_partial"),
        ],
    )
    def test_passed(
        self,
        request: pytest.FixtureRequest,
        fixture_name: str,
        expected: bool,
    ) -> None:
        project = request.getfixturevalue(fixture_name)
        r = check_diataxis_nav(project)
        assert r.passed is expected


@pytest.fixture
def flat_nav_project(tmp_path: Path) -> Path:
    (tmp_path / "mkdocs.yml").write_text("nav:\n  - Home: index.md\n")
    return tmp_path


@pytest.fixture
def partial_nav_project(tmp_path: Path) -> Path:
    mkdocs = "nav:\n  - Tutorials:\n    - t.md\n  - Reference:\n    - r.md\n"
    (tmp_path / "mkdocs.yml").write_text(mkdocs)
    return tmp_path


def test_diataxis_nav_workspace_fallback(workspace_member: Path) -> None:
    """Workspace member falls back to root mkdocs.yml for nav check."""
    result = check_diataxis_nav(workspace_member)
    assert result.passed is True
