from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.checks.docs import check_docs_plugins

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

NAV_ONLY = """site_name: pkg\ndocs_dir: docs\nnav:\n  - Overview: index.md\n"""

FULL_PLUGINS = (
    "site_name: workspace\nplugins:\n  - search\n"
    "  - gen-files\n  - literate-nav\n  - mkdocstrings\n"
)

PARTIAL_PLUGINS_GEN = """site_name: pkg\nplugins:\n  - gen-files\n"""

PARTIAL_PLUGINS_LIT_MKD = (
    """site_name: workspace\nplugins:\n  - literate-nav\n  - mkdocstrings\n"""
)


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """Create a workspace member layout: workspace/packages/pkg/."""
    pkg = tmp_path / "packages" / "pkg"
    pkg.mkdir(parents=True)
    return pkg


# ---------------------------------------------------------------------------
# Unit tests (from test_spec)
# ---------------------------------------------------------------------------


def test_docs_plugins_local_nav_only_root_has_plugins(
    workspace: Path,
    tmp_path: Path,
) -> None:
    """Local nav-only mkdocs + root with all plugins -> passed."""
    (workspace / "mkdocs.yml").write_text(NAV_ONLY)
    (tmp_path / "mkdocs.yml").write_text(FULL_PLUGINS)

    result = check_docs_plugins(workspace)

    assert result.passed is True


def test_docs_plugins_local_nav_only_no_root_plugins(
    workspace: Path,
    tmp_path: Path,
) -> None:
    """Local nav-only + root also nav-only -> fails, missing all 3."""
    (workspace / "mkdocs.yml").write_text(NAV_ONLY)
    (tmp_path / "mkdocs.yml").write_text(NAV_ONLY)

    result = check_docs_plugins(workspace)

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

    result = check_docs_plugins(workspace)

    assert result.passed is True


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_docs_plugins_local_has_all_plugins_workspace_member(
    workspace: Path,
) -> None:
    """Workspace member with self-contained mkdocs passes without root check."""
    (workspace / "mkdocs.yml").write_text(FULL_PLUGINS)
    # No root mkdocs.yml — should still pass

    result = check_docs_plugins(workspace)

    assert result.passed is True


def test_docs_plugins_not_workspace_member(tmp_path: Path) -> None:
    """Standalone project (not under packages/) — no fallback, normal behavior."""
    project = tmp_path / "standalone"
    project.mkdir()
    (project / "mkdocs.yml").write_text(NAV_ONLY)

    result = check_docs_plugins(project)

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

    result = check_docs_plugins(workspace)

    assert result.passed is False
    assert "gen-files" in result.details[0]
