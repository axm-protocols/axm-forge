from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.checks.docs import (
    check_diataxis_nav,
    check_docs_plugins,
    check_mkdocs_exists,
)

MKDOCS_FULL = """
site_name: Test
nav:
  - Tutorial: tutorial.md
  - How-To: howto.md
  - Reference: reference.md
  - Explanation: explanation.md
plugins:
  - gen-files
  - literate-nav
  - mkdocstrings
"""


# --- Fixtures ---


@pytest.fixture()
def workspace_member(tmp_path: Path) -> Path:
    """Create a workspace member layout: tmp/packages/pkg/ with mkdocs.yml at root."""
    pkg = tmp_path / "packages" / "pkg"
    pkg.mkdir(parents=True)
    (tmp_path / "mkdocs.yml").write_text(MKDOCS_FULL)
    return pkg


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


# --- Unit tests: check_mkdocs_exists ---


def test_mkdocs_exists_workspace_member(workspace_member: Path) -> None:
    """Workspace member falls back to root mkdocs.yml."""
    result = check_mkdocs_exists(workspace_member)
    assert result.passed is True


def test_mkdocs_exists_standalone(standalone_project: Path) -> None:
    """Standalone project with no mkdocs.yml fails."""
    result = check_mkdocs_exists(standalone_project)
    assert result.passed is False


# --- Unit tests: check_diataxis_nav ---


def test_diataxis_nav_workspace_fallback(workspace_member: Path) -> None:
    """Workspace member falls back to root mkdocs.yml for nav check."""
    result = check_diataxis_nav(workspace_member)
    assert result.passed is True


# --- Unit tests: check_docs_plugins ---


def test_docs_plugins_workspace_fallback(workspace_member: Path) -> None:
    """Workspace member falls back to root mkdocs.yml for plugins check."""
    result = check_docs_plugins(workspace_member)
    assert result.passed is True


# --- Edge cases ---


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
