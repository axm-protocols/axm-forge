"""Unit tests for GitPullTool."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from axm_git.tools.pull import GitPullTool


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


class TestGitPullTool:
    """Test GitPullTool behavior."""

    def test_name(self) -> None:
        """Tool registers under the git_pull name."""
        assert GitPullTool().name == "git_pull"

    @patch("axm_git.tools.pull.run_git")
    def test_pull_success(self, mock_git: MagicMock) -> None:
        """A successful pull returns the remote and branch in data."""
        mock_git.side_effect = [
            _ok(),  # rev-parse --git-dir
            _ok(stdout="Already up to date."),  # pull
        ]
        result = GitPullTool().execute(path="/repo")
        assert result.success
        assert result.data["pulled"] is True
        assert result.data["remote"] == "origin"
        assert result.data["branch"] == "main"

    @patch("axm_git.tools.pull.run_git")
    def test_defaults_in_call_args(self, mock_git: MagicMock) -> None:
        """Defaults issue ``pull origin main``."""
        mock_git.side_effect = [_ok(), _ok()]
        GitPullTool().execute(path="/repo")

        pull_call = mock_git.call_args_list[1]
        assert pull_call[0][0] == ["pull", "origin", "main"]

    @patch("axm_git.tools.pull.run_git")
    def test_custom_remote_branch(self, mock_git: MagicMock) -> None:
        """Custom remote and branch flow into the pull command and data."""
        mock_git.side_effect = [_ok(), _ok()]
        result = GitPullTool().execute(
            remote="upstream", branch="develop", path="/repo"
        )
        assert result.success
        assert result.data["remote"] == "upstream"
        assert result.data["branch"] == "develop"

        pull_call = mock_git.call_args_list[1]
        assert pull_call[0][0] == ["pull", "upstream", "develop"]

    @patch("axm_git.tools.pull.run_git")
    def test_pull_fails(self, mock_git: MagicMock) -> None:
        """A failing pull returns failure."""
        mock_git.side_effect = [
            _ok(),  # rev-parse
            _fail(stderr="fatal: couldn't find remote ref main"),  # pull
        ]
        result = GitPullTool().execute(path="/repo")
        assert not result.success
        assert "git pull failed" in (result.error or "")

    @patch("axm_git.tools.pull.run_git")
    def test_not_git_repo(self, mock_git: MagicMock) -> None:
        """A non-git directory returns failure via not_a_repo_error."""
        mock_git.side_effect = [
            _fail(stderr="fatal: not a git repository"),
        ]
        with patch("axm_git.tools.pull.not_a_repo_error") as mock_err:
            mock_err.return_value = MagicMock(
                success=False, error="not a repo", data=None
            )
            result = GitPullTool().execute(path="/not-a-repo")
            assert not result.success
            mock_err.assert_called_once()
