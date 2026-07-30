"""Failure- and nominal-path integration tests for GitWorktreeTool.

Every repo is a throwaway created under ``tmp_path`` (never the axm-forge
working repo). Failures are simulated with fresh/nonexistent paths, never a
real network operation.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_git.tools.worktree import GitWorktreeTool

pytestmark = pytest.mark.integration


def _init_repo(root: Path) -> str:
    """Init a throwaway repo with one commit; return its default branch."""
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.io"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=root, check=True)
    (root / "f.txt").write_text("x")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=root, check=True)
    return subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def test_add_to_fresh_sibling_path_succeeds(tmp_path: Path) -> None:
    """Nominal: a worktree at a not-yet-existing sibling path is created.

    Regression for the P0-1 false-crash: git-root resolution runs on the
    repo (``path``), so a fresh ``worktree_path`` no longer raises a raw
    ``FileNotFoundError``.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    branch = _init_repo(repo)
    dest = tmp_path / "wt-fresh"  # does not exist yet

    result = GitWorktreeTool().execute(
        action="add",
        path=str(repo),
        worktree_path=str(dest),
        branch="feat/x",
        base=branch,
    )
    assert result.success
    assert (dest / ".git").exists()
    assert result.data["path"] == str(dest.resolve())


def test_add_fresh_path_without_worktree_path_fails_cleanly(tmp_path: Path) -> None:
    """Failure path: legacy form on a nonexistent path returns a ToolResult.

    Passing only ``path`` (legacy) at a nonexistent location must degrade to
    ``success=False`` with a readable error, not a raw ``FileNotFoundError``.
    """
    dest = tmp_path / "nope"  # never created, not inside any repo

    result = GitWorktreeTool().execute(action="add", path=str(dest), branch="b")
    assert not result.success
    assert "not a git repository" in (result.error or "")


def test_list_on_non_git_dir_fails(tmp_path: Path) -> None:
    """Failure path: listing worktrees outside a repo is a readable error."""
    result = GitWorktreeTool().execute(action="list", path=str(tmp_path))
    assert not result.success
    assert result.error


def test_invalid_action_fails(tmp_path: Path) -> None:
    """Failure path: an unknown action is rejected before touching git."""
    result = GitWorktreeTool().execute(action="teleport", path=str(tmp_path))
    assert not result.success
    assert "Invalid action" in (result.error or "")
