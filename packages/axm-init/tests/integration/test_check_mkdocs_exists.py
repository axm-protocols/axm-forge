"""Split from ``test_diataxis_docs_layout_requirements.py``."""

from pathlib import Path

import pytest

from axm_init.checks.docs import check_mkdocs_exists
from tests.integration._helpers import MKDOCS_FULL


class TestCheckMkdocsExists:
    def test_pass(self, gold_project: Path) -> None:
        r = check_mkdocs_exists(gold_project)
        assert r.passed is True

    def test_fail(self, empty_project: Path) -> None:
        r = check_mkdocs_exists(empty_project)
        assert r.passed is False


@pytest.fixture()
def standalone_project(tmp_path: Path) -> Path:
    """Create a standalone project with no mkdocs.yml."""
    project = tmp_path / "project"
    project.mkdir(parents=True)
    return project


@pytest.fixture()
def workspace_member_no_root_mkdocs(tmp_path: Path) -> Path:
    """Parent named 'packages' but no workspace root mkdocs.yml."""
    pkg = tmp_path / "packages" / "bar"
    pkg.mkdir(parents=True)
    return pkg


@pytest.fixture()
def workspace_member_with_local_mkdocs(tmp_path: Path) -> Path:
    """Both local and workspace mkdocs.yml exist — local should win."""
    pkg = tmp_path / "packages" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "mkdocs.yml").write_text(MKDOCS_FULL)
    (tmp_path / "mkdocs.yml").write_text(MKDOCS_FULL)
    return pkg


def test_mkdocs_exists_workspace_member(workspace_member: Path) -> None:
    """Workspace member falls back to root mkdocs.yml."""
    result = check_mkdocs_exists(workspace_member)
    assert result.passed is True


def test_mkdocs_exists_standalone(standalone_project: Path) -> None:
    """Standalone project with no mkdocs.yml fails."""
    result = check_mkdocs_exists(standalone_project)
    assert result.passed is False


def test_mkdocs_exists_packages_parent_no_workspace_mkdocs(
    workspace_member_no_root_mkdocs: Path,
) -> None:
    """Parent named 'packages' but no workspace mkdocs.yml — should fail."""
    result = check_mkdocs_exists(workspace_member_no_root_mkdocs)
    assert result.passed is False


def test_mkdocs_exists_local_preferred_over_workspace(
    workspace_member_with_local_mkdocs: Path,
) -> None:
    """When both local and workspace mkdocs exist, local wins."""
    result = check_mkdocs_exists(workspace_member_with_local_mkdocs)
    assert result.passed is True
    assert result.message == "mkdocs.yml found"
