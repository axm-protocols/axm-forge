"""Unit tests for checks._workspace — pure context detection (no real I/O)."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from axm_init.checks._workspace import ProjectContext, detect_context

STANDALONE_TOML = dedent("""\
    [project]
    name = "standalone-pkg"

    [build-system]
    requires = ["hatchling"]
    build-backend = "hatchling.build"
""")


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


@pytest.fixture()
def member_path(workspace_root__from_workspace_context_detection: Path) -> Path:
    """Path to a member package inside the workspace."""
    return workspace_root__from_workspace_context_detection / "packages" / "pkg-a"


@pytest.fixture()
def standalone_project(tmp_path: Path) -> Path:
    """A standalone package (no workspace)."""
    (tmp_path / "pyproject.toml").write_text(STANDALONE_TOML)
    return tmp_path


def test_project_context_exposes_a_paper_member() -> None:
    """AC1: the enum gains a PAPER member valued ``paper`` (four members)."""
    assert ProjectContext.PAPER.value == "paper"
    assert len(list(ProjectContext)) == 5


def test_context_tables_key_the_paper_member() -> None:
    """AC5: skip and redirect tables key PAPER and validation still passes."""
    from axm_init.core.checker import (
        REDIRECT_BY_CONTEXT,
        SKIP_BY_CONTEXT,
        validate_context_tables,
    )

    validate_context_tables()

    assert ProjectContext.PAPER in SKIP_BY_CONTEXT
    assert ProjectContext.PAPER in REDIRECT_BY_CONTEXT


def test_project_context_exposes_an_experiment_member() -> None:
    """AC1: the enum gains an EXPERIMENT member valued ``experiment``."""
    assert ProjectContext.EXPERIMENT.value == "experiment"
    assert "experiment" in {ctx.value for ctx in ProjectContext}


def test_experiment_manifest_marker_accepts_both_declared_keys() -> None:
    """AC2: a mapping declaring contract_version AND id is a manifest marker."""
    from axm_init.checks._workspace import _is_experiment_manifest

    assert _is_experiment_manifest("contract_version: 1\nid: 01-demo\n") is True


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("id: x", id="missing_contract_version"),
        pytest.param("contract_version: 1", id="missing_id"),
        pytest.param("- a\n- b", id="not_a_mapping"),
        pytest.param("::", id="invalid_yaml"),
    ],
)
def test_experiment_manifest_marker_rejects_partial_and_malformed(text: str) -> None:
    """AC3: partial mapping, non-mapping and invalid YAML are not markers."""
    from axm_init.checks._workspace import _is_experiment_manifest

    assert _is_experiment_manifest(text) is False
