"""Split from ``test_diataxis_docs_layout_requirements.py``."""

from pathlib import Path

import pytest

from axm_init.checks.docs import check_plugins


class TestCheckDocsPlugins:
    def test_pass(self, gold_project: Path) -> None:
        r = check_plugins(gold_project)
        assert r.passed is True

    def test_fail_no_plugins(self, tmp_path: Path) -> None:
        (tmp_path / "mkdocs.yml").write_text("site_name: x\n")
        r = check_plugins(tmp_path)
        assert r.passed is False


def test_docs_plugins_workspace_fallback(workspace_member: Path) -> None:
    """Workspace member falls back to root mkdocs.yml for plugins check."""
    result = check_plugins(workspace_member)
    assert result.passed is True


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

    result = check_plugins(workspace_project)

    assert result.passed is True
    assert result.message == "All plugins configured"


def test_workspace_no_root_mkdocs(workspace_project: Path) -> None:
    """Local missing plugins, no root mkdocs.yml -> fails."""
    local_mkdocs = workspace_project / "mkdocs.yml"
    local_mkdocs.write_text("plugins:\n  - mkdocstrings\n")

    result = check_plugins(workspace_project)

    assert result.passed is False
    assert "gen-files" in result.details[0]
    assert "literate-nav" in result.details[0]


def test_non_workspace_no_fallback(standalone_project: Path) -> None:
    """Not a workspace member -> no fallback attempted, fails if missing."""
    local_mkdocs = standalone_project / "mkdocs.yml"
    local_mkdocs.write_text("plugins:\n  - mkdocstrings\n")

    result = check_plugins(standalone_project)

    assert result.passed is False
    assert "2" in result.message
    assert "gen-files" in result.details[0]
    assert "literate-nav" in result.details[0]


FULL_PLUGINS = (
    "site_name: workspace\nplugins:\n  - search\n"
    "  - gen-files\n  - literate-nav\n  - mkdocstrings\n"
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

NAV_ONLY = """site_name: pkg\ndocs_dir: docs\nnav:\n  - Overview: index.md\n"""

PARTIAL_PLUGINS_LIT_MKD = (
    """site_name: workspace\nplugins:\n  - literate-nav\n  - mkdocstrings\n"""
)

PARTIAL_PLUGINS_GEN = """site_name: pkg\nplugins:\n  - gen-files\n"""


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """Create a workspace member layout: workspace/packages/pkg/."""
    pkg = tmp_path / "packages" / "pkg"
    pkg.mkdir(parents=True)
    return pkg


def test_docs_plugins_local_nav_only_root_has_plugins(
    workspace: Path,
    tmp_path: Path,
) -> None:
    """Local nav-only mkdocs + root with all plugins -> passed."""
    (workspace / "mkdocs.yml").write_text(NAV_ONLY)
    (tmp_path / "mkdocs.yml").write_text(FULL_PLUGINS)

    result = check_plugins(workspace)

    assert result.passed is True


def test_docs_plugins_local_nav_only_no_root_plugins(
    workspace: Path,
    tmp_path: Path,
) -> None:
    """Local nav-only + root also nav-only -> fails, missing all 3."""
    (workspace / "mkdocs.yml").write_text(NAV_ONLY)
    (tmp_path / "mkdocs.yml").write_text(NAV_ONLY)

    result = check_plugins(workspace)

    assert result.passed is False
    assert "gen-files" in result.details[0]
    assert "literate-nav" in result.details[0]
    assert "mkdocstrings" in result.details[0]


def test_docs_plugins_local_has_some_root_has_rest(
    workspace: Path,
    tmp_path: Path,
) -> None:
    """Local has gen-files, root has literate-nav + mkdocstrings -> passed."""
    (workspace / "mkdocs.yml").write_text(PARTIAL_PLUGINS_GEN)
    (tmp_path / "mkdocs.yml").write_text(PARTIAL_PLUGINS_LIT_MKD)

    result = check_plugins(workspace)

    assert result.passed is True


def test_docs_plugins_local_has_all_plugins_workspace_member(
    workspace: Path,
) -> None:
    """Workspace member with self-contained mkdocs passes without root check."""
    (workspace / "mkdocs.yml").write_text(FULL_PLUGINS)
    # No root mkdocs.yml — should still pass

    result = check_plugins(workspace)

    assert result.passed is True


def test_docs_plugins_not_workspace_member(tmp_path: Path) -> None:
    """Standalone project (not under packages/) — no fallback, normal behavior."""
    project = tmp_path / "standalone"
    project.mkdir()
    (project / "mkdocs.yml").write_text(NAV_ONLY)

    result = check_plugins(project)

    assert result.passed is False
    assert "gen-files" in result.details[0]
    assert "literate-nav" in result.details[0]
    assert "mkdocstrings" in result.details[0]


def test_docs_plugins_workspace_member_no_root_mkdocs(
    workspace: Path,
) -> None:
    """Member layout but no root mkdocs.yml -> reports missing plugins."""
    (workspace / "mkdocs.yml").write_text(NAV_ONLY)
    # No root mkdocs.yml exists

    result = check_plugins(workspace)

    assert result.passed is False
    assert "gen-files" in result.details[0]
