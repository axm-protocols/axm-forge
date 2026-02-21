"""Unit tests for GitBranchTool."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from axm_git.tools.branch import GitBranchTool


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


class TestGitBranchTool:
    """Test GitBranchTool behavior."""

    def test_name(self) -> None:
        assert GitBranchTool().name == "git_branch"

    @patch("axm_git.tools.branch.run_git")
    def test_create_branch(self, mock_git: MagicMock) -> None:
        """Create branch and verify success."""
        mock_git.side_effect = [
            _ok(),  # rev-parse --git-dir
            _ok(stderr="Switched to a new branch 'feat/x'"),  # checkout -b
            _ok(stdout="feat/x\n"),  # branch --show-current
        ]
        result = GitBranchTool().execute(name="feat/x", path="/repo")
        assert result.success
        assert result.data["branch"] == "feat/x"

        # Verify checkout -b was called.
        checkout_call = mock_git.call_args_list[1]
        assert checkout_call[0][0] == ["checkout", "-b", "feat/x"]

    @patch("axm_git.tools.branch.run_git")
    def test_create_from_ref(self, mock_git: MagicMock) -> None:
        """Create branch from a specific ref."""
        mock_git.side_effect = [
            _ok(),  # rev-parse --git-dir
            # checkout -b feat/x v1.0.0
            _ok(stderr="Switched to a new branch 'feat/x'"),
            _ok(stdout="feat/x\n"),  # branch --show-current
        ]
        result = GitBranchTool().execute(
            name="feat/x",
            from_ref="v1.0.0",
            path="/repo",
        )
        assert result.success
        assert result.data["branch"] == "feat/x"

        args = mock_git.call_args_list[1][0][0]
        assert args == ["checkout", "-b", "feat/x", "v1.0.0"]

    @patch("axm_git.tools.branch.run_git")
    def test_checkout_only(self, mock_git: MagicMock) -> None:
        """Checkout existing branch without creating."""
        mock_git.side_effect = [
            _ok(),  # rev-parse --git-dir
            _ok(stderr="Switched to branch 'feat/x'"),  # checkout (no -b)
            _ok(stdout="feat/x\n"),  # branch --show-current
        ]
        result = GitBranchTool().execute(
            name="feat/x",
            checkout_only=True,
            path="/repo",
        )
        assert result.success
        assert result.data["branch"] == "feat/x"

        checkout_call = mock_git.call_args_list[1]
        assert checkout_call[0][0] == ["checkout", "feat/x"]

    @patch("axm_git.tools.branch.run_git")
    def test_create_existing_fails(self, mock_git: MagicMock) -> None:
        """Creating an already-existing branch returns failure."""
        mock_git.side_effect = [
            _ok(),  # rev-parse --git-dir
            _fail(stderr="fatal: a branch named 'main' already exists"),
        ]
        result = GitBranchTool().execute(name="main", path="/repo")
        assert not result.success
        assert "already exists" in (result.error or "")

    @patch("axm_git.tools.branch.run_git")
    def test_not_git_repo(self, mock_git: MagicMock) -> None:
        """Non-git directory returns failure with suggestions."""
        mock_git.side_effect = [
            _fail(stderr="fatal: not a git repository"),
        ]
        with patch("axm_git.tools.branch.not_a_repo_error") as mock_err:
            mock_err.return_value = MagicMock(success=False, error="not a repo")
            result = GitBranchTool().execute(name="feat/x", path="/not-a-repo")
            assert not result.success
            mock_err.assert_called_once()

    @patch("axm_git.tools.branch.run_git")
    def test_branch_with_slashes(self, mock_git: MagicMock) -> None:
        """Branch names with nested slashes work."""
        mock_git.side_effect = [
            _ok(),  # rev-parse
            _ok(),  # checkout -b
            _ok(stdout="feat/sub/branch\n"),
        ]
        result = GitBranchTool().execute(name="feat/sub/branch", path="/repo")
        assert result.success
        assert result.data["branch"] == "feat/sub/branch"

    @patch("axm_git.tools.branch.run_git")
    def test_invalid_from_ref(self, mock_git: MagicMock) -> None:
        """Invalid from_ref returns failure."""
        mock_git.side_effect = [
            _ok(),  # rev-parse
            _fail(stderr="fatal: 'nonexistent' is not a commit"),
        ]
        result = GitBranchTool().execute(
            name="feat/x",
            from_ref="nonexistent",
            path="/repo",
        )
        assert not result.success
        assert "not a commit" in (result.error or "")
