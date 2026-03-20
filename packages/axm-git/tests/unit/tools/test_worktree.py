"""Unit tests for GitWorktreeTool."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from axm_git.tools.worktree import GitWorktreeTool


def _ok(
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout=stdout,
        stderr=stderr,
    )


def _fail(
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=[],
        returncode=128,
        stdout=stdout,
        stderr=stderr,
    )


_PORCELAIN_OUTPUT = """\
worktree /repo
HEAD abc1234567890abcdef1234567890abcdef123456
branch refs/heads/main

worktree /repo/wt-feat
HEAD def4567890abcdef1234567890abcdef12345678
branch refs/heads/feat/x

"""


class TestGitWorktreeTool:
    """Test GitWorktreeTool behavior."""

    def test_name(self) -> None:
        assert GitWorktreeTool().name == "git_worktree"

    @patch("axm_git.tools.worktree.run_git")
    @patch("axm_git.tools.worktree.find_git_root")
    def test_worktree_add(
        self,
        mock_root: MagicMock,
        mock_git: MagicMock,
    ) -> None:
        """Add action creates a new worktree with branch."""
        mock_root.return_value = MagicMock()
        mock_git.return_value = _ok(stderr="Preparing worktree")

        result = GitWorktreeTool().execute(
            action="add",
            path="/repo/wt-feat",
            branch="feat/x",
            base="main",
        )
        assert result.success
        assert result.data["branch"] == "feat/x"

        cmd = mock_git.call_args[0][0]
        assert cmd[:2] == ["worktree", "add"]
        assert "-b" in cmd
        assert "feat/x" in cmd
        assert "main" in cmd

    @patch("axm_git.tools.worktree.run_git")
    @patch("axm_git.tools.worktree.find_git_root")
    def test_worktree_remove(
        self,
        mock_root: MagicMock,
        mock_git: MagicMock,
    ) -> None:
        """Remove action removes an existing worktree."""
        mock_root.return_value = MagicMock()
        mock_git.return_value = _ok()

        result = GitWorktreeTool().execute(
            action="remove",
            path="/repo/wt-feat",
        )
        assert result.success
        assert "removed" in result.data

        cmd = mock_git.call_args[0][0]
        assert cmd[:2] == ["worktree", "remove"]

    @patch("axm_git.tools.worktree.run_git")
    @patch("axm_git.tools.worktree.find_git_root")
    def test_worktree_remove_force(
        self,
        mock_root: MagicMock,
        mock_git: MagicMock,
    ) -> None:
        """Force flag adds --force to remove command."""
        mock_root.return_value = MagicMock()
        mock_git.return_value = _ok()

        GitWorktreeTool().execute(
            action="remove",
            path="/repo/wt-feat",
            force=True,
        )

        cmd = mock_git.call_args[0][0]
        assert "--force" in cmd

    @patch("axm_git.tools.worktree.run_git")
    @patch("axm_git.tools.worktree.find_git_root")
    def test_worktree_list_parse(
        self,
        mock_root: MagicMock,
        mock_git: MagicMock,
    ) -> None:
        """List action parses porcelain output into dicts."""
        mock_root.return_value = MagicMock()
        mock_git.return_value = _ok(stdout=_PORCELAIN_OUTPUT)

        result = GitWorktreeTool().execute(action="list", path="/repo")
        assert result.success

        wts = result.data["worktrees"]
        assert len(wts) == 2
        assert wts[0]["path"] == "/repo"
        assert wts[0]["branch"] == "refs/heads/main"
        assert wts[1]["path"] == "/repo/wt-feat"
        assert wts[1]["branch"] == "refs/heads/feat/x"
        assert "HEAD" in wts[0]

    def test_worktree_invalid_action(self) -> None:
        """Invalid action returns failure without calling git."""
        result = GitWorktreeTool().execute(action="invalid", path="/repo")
        assert not result.success
        assert "Invalid action" in (result.error or "")

    @patch("axm_git.tools.worktree.find_git_root")
    def test_not_git_repo(self, mock_root: MagicMock) -> None:
        """Non-git directory returns failure."""
        mock_root.return_value = None

        with patch("axm_git.tools.worktree.not_a_repo_error") as mock_err:
            mock_err.return_value = MagicMock(success=False, error="not a repo")
            result = GitWorktreeTool().execute(action="list", path="/not-a-repo")
            assert not result.success
            mock_err.assert_called_once()

    @patch("axm_git.tools.worktree.run_git")
    @patch("axm_git.tools.worktree.find_git_root")
    def test_worktree_add_existing_path(
        self,
        mock_root: MagicMock,
        mock_git: MagicMock,
    ) -> None:
        """Add at existing path surfaces git error."""
        mock_root.return_value = MagicMock()
        mock_git.return_value = _fail(stderr="fatal: '/repo/wt-feat' already exists")

        result = GitWorktreeTool().execute(
            action="add",
            path="/repo/wt-feat",
            branch="feat/x",
        )
        assert not result.success
        assert "already exists" in (result.error or "")
