"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_git.core.runner import run_git


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
