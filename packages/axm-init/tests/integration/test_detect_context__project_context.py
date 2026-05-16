"""Tests for checks._workspace — workspace context detection."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from axm_init.checks._workspace import (
    ProjectContext,
    detect_context,
)
from tests.integration._helpers import STANDALONE_TOML

MEMBER_TOML = dedent("""\
    [project]
    name = "member-pkg"
""")


# ---------------------------------------------------------------------------
# TestDetectContext
# ---------------------------------------------------------------------------


class TestDetectContext:
    @pytest.mark.parametrize(
        ("fixture_name", "expected"),
        [
            pytest.param(
                "standalone_project", ProjectContext.STANDALONE, id="standalone"
            ),
            pytest.param(
                "workspace_root__from_workspace_context_detection",
                ProjectContext.WORKSPACE,
                id="workspace",
            ),
            pytest.param("member_path", ProjectContext.MEMBER, id="member"),
        ],
    )
    def test_detect(
        self,
        request: pytest.FixtureRequest,
        fixture_name: str,
        expected: ProjectContext,
    ) -> None:
        path = request.getfixturevalue(fixture_name)
        assert detect_context(path) == expected


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(None, id="missing_pyproject"),
        pytest.param("{{invalid toml!!", id="corrupt_toml"),
    ],
)
def test_detect_context_falls_back_to_standalone(
    tmp_path: Path, content: str | None
) -> None:
    """Missing or corrupt pyproject.toml → STANDALONE (graceful fallback)."""
    if content is not None:
        (tmp_path / "pyproject.toml").write_text(content)
    assert detect_context(tmp_path) == ProjectContext.STANDALONE


@pytest.fixture()
def member_path(workspace_root__from_workspace_context_detection: Path) -> Path:
    """Path to a member package inside the workspace."""
    return workspace_root__from_workspace_context_detection / "packages" / "pkg-a"


@pytest.fixture()
def standalone_project(tmp_path: Path) -> Path:
    """A standalone package (no workspace)."""
    (tmp_path / "pyproject.toml").write_text(STANDALONE_TOML)
    return tmp_path


# ---------------------------------------------------------------------------
