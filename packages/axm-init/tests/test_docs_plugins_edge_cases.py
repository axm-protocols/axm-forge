from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.checks.docs import check_docs_plugins


@pytest.fixture
def workspace_project(tmp_path: Path) -> Path:
    """Create a workspace member project: .../packages/my-pkg/."""
    packages = tmp_path / "packages"
    project = packages / "my-pkg"
    project.mkdir(parents=True)
    return project


@pytest.fixture
def standalone_project(tmp_path: Path) -> Path:
    """Create a standalone project (not a workspace member)."""
    project = tmp_path / "my-standalone"
    project.mkdir(parents=True)
    return project


def test_workspace_root_resolves_all_missing(workspace_project: Path) -> None:
    """Local mkdocs missing 2 plugins, root has both -> passes."""
    local_mkdocs = workspace_project / "mkdocs.yml"
    local_mkdocs.write_text("plugins:\n  - mkdocstrings\n")

    root_mkdocs = workspace_project.parent.parent / "mkdocs.yml"
    root_mkdocs.write_text(
        "plugins:\n  - gen-files\n  - literate-nav\n  - mkdocstrings\n"
    )

    result = check_docs_plugins(workspace_project)

    assert result.passed is True
    assert result.message == "All plugins configured"


def test_workspace_no_root_mkdocs(workspace_project: Path) -> None:
    """Local missing plugins, no root mkdocs.yml -> fails."""
    local_mkdocs = workspace_project / "mkdocs.yml"
    local_mkdocs.write_text("plugins:\n  - mkdocstrings\n")

    result = check_docs_plugins(workspace_project)

    assert result.passed is False
    assert "gen-files" in result.details[0]
    assert "literate-nav" in result.details[0]


def test_non_workspace_no_fallback(standalone_project: Path) -> None:
    """Not a workspace member -> no fallback attempted, fails if missing."""
    local_mkdocs = standalone_project / "mkdocs.yml"
    local_mkdocs.write_text("plugins:\n  - mkdocstrings\n")

    result = check_docs_plugins(standalone_project)

    assert result.passed is False
    assert "2" in result.message
    assert "gen-files" in result.details[0]
    assert "literate-nav" in result.details[0]
