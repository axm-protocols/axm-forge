"""Failure-path integration tests for GitPullTool.

Throwaway repos under ``tmp_path``; a nonexistent remote simulates the
pull-failure path (never a real network pull).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_git.tools.pull import GitPullTool

pytestmark = pytest.mark.integration


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.io"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=root, check=True)
    (root / "f.txt").write_text("x")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=root, check=True)


def test_pull_on_non_git_dir_fails(tmp_path: Path) -> None:
    """Failure path: pulling outside a repo returns a readable not-a-repo error."""
    result = GitPullTool().execute(path=str(tmp_path))
    assert not result.success
    assert result.error


def test_pull_from_missing_remote_fails(tmp_path: Path) -> None:
    """Failure path: pulling a remote that does not exist is a hard failure.

    The remote ``origin`` is never configured, so ``git pull`` fails and the
    tool must surface ``success=False`` with the git error text.
    """
    _init_repo(tmp_path)
    result = GitPullTool().execute(path=str(tmp_path), remote="origin", branch="main")
    assert not result.success
    assert "git pull failed" in (result.error or "")
