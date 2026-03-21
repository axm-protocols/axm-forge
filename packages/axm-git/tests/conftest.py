"""Shared pytest fixtures."""

from __future__ import annotations

import shutil
from collections.abc import Generator
from pathlib import Path

import pytest

from axm_git.core.runner import run_git

_AXM_WORKTREES_DIR = Path("/tmp/axm-worktrees")


@pytest.fixture(autouse=True)
def _cleanup_axm_worktrees() -> Generator[None, None, None]:
    """Remove any /tmp/axm-worktrees/<id> dirs created during the test."""
    before = set(_AXM_WORKTREES_DIR.iterdir()) if _AXM_WORKTREES_DIR.exists() else set()
    yield
    if _AXM_WORKTREES_DIR.exists():
        for entry in _AXM_WORKTREES_DIR.iterdir():
            if entry not in before:
                shutil.rmtree(entry, ignore_errors=True)


@pytest.fixture
def sample_data() -> dict[str, str]:
    """Provide sample test data."""
    return {"key": "value"}


@pytest.fixture
def tmp_git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repo with an initial commit."""
    run_git(["init", "-b", "main"], tmp_path)
    run_git(["config", "user.email", "test@test.com"], tmp_path)
    run_git(["config", "user.name", "Test"], tmp_path)
    (tmp_path / ".gitkeep").touch()
    run_git(["add", "."], tmp_path)
    run_git(["commit", "-m", "init"], tmp_path)
    return tmp_path


@pytest.fixture
def tmp_workspace_repo(tmp_path: Path) -> tuple[Path, Path]:
    """Create a workspace git repo with a nested package directory.

    Layout::

        tmp_path/workspace/          ← git root
            .gitkeep
            packages/pkg/            ← package dir (returned second)
                src/
                    hello.py

    Returns:
        (git_root, package_dir) tuple.
    """
    workspace = tmp_path / "workspace"
    pkg_dir = workspace / "packages" / "pkg"
    pkg_dir.mkdir(parents=True)

    run_git(["init", "-b", "main"], workspace)
    run_git(["config", "user.email", "test@test.com"], workspace)
    run_git(["config", "user.name", "Test"], workspace)
    (workspace / ".gitkeep").touch()
    (pkg_dir / "src").mkdir()
    (pkg_dir / "src" / "hello.py").write_text("# init\n")
    run_git(["add", "."], workspace)
    run_git(["commit", "-m", "init"], workspace)
    return workspace, pkg_dir


@pytest.fixture
def tmp_git_repo_with_branch(tmp_git_repo: Path) -> Path:
    """Create a git repo with a session branch containing one commit.

    The repo starts on ``main`` with one commit, then creates
    ``axm/abc`` with an additional file committed on it.
    The working tree is left on the session branch.
    """
    run_git(["checkout", "-b", "axm/abc"], tmp_git_repo)
    (tmp_git_repo / "session_file.txt").write_text("session work")
    run_git(["add", "."], tmp_git_repo)
    run_git(["commit", "-m", "session commit"], tmp_git_repo)
    return tmp_git_repo
