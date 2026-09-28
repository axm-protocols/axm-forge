"""read_workspace_identity resolves member links from the workspace root files."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.core import WorkspaceIdentity, read_workspace_identity

pytestmark = pytest.mark.integration


def test_mkdocs_links_win_over_the_root_project_name(tmp_path: Path) -> None:
    """Regression: a `<repo>-workspace` root name no longer leaks into URLs."""
    root = tmp_path / "checkout"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "axm-nexus-workspace"\n')
    (root / "mkdocs.yml").write_text(
        "site_name: AXM Nexus\n"
        "site_url: https://nexus.axm-protocols.io/\n"
        "repo_url: https://github.com/axm-protocols/axm-nexus\n"
        "markdown_extensions:\n"
        "  - pymdownx.emoji:\n"
        "      emoji_index: !!python/name:material.extensions.emoji.twemoji\n"
    )

    assert read_workspace_identity(root, "someone-else") == WorkspaceIdentity(
        name="axm-nexus-workspace",
        repository="axm-protocols/axm-nexus",
        site_url="https://nexus.axm-protocols.io",
    )


def test_project_urls_are_the_fallback(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "axm-forge-workspace"\n\n[project.urls]\n'
        'Repository = "https://github.com/axm-protocols/axm-forge.git"\n'
        'Documentation = "https://forge.axm-protocols.io"\n'
    )

    identity = read_workspace_identity(tmp_path, "acme")

    assert identity.repository == "axm-protocols/axm-forge"
    assert identity.site_url == "https://forge.axm-protocols.io"


def test_without_metadata_the_checkout_directory_names_the_repository(
    tmp_path: Path,
) -> None:
    root = tmp_path / "my-repo"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "my-repo-workspace"\n')

    assert read_workspace_identity(root, "acme") == WorkspaceIdentity(
        name="my-repo-workspace",
        repository="acme/my-repo",
        site_url="https://acme.github.io/my-repo",
    )
