"""Unit tests for GitPRTool."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from axm_git.tools.pr import GitPRTool


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


_PR_URL = "https://github.com/axm-protocols/axm-git/pull/42"


class TestGitPRTool:
    """Test GitPRTool behavior."""

    def test_name(self) -> None:
        assert GitPRTool().name == "git_pr"

    @patch("axm_git.tools.pr.gh_available", return_value=True)
    @patch("axm_git.tools.pr.run_gh")
    @patch("axm_git.tools.pr.run_git")
    def test_pr_create(
        self,
        mock_git: MagicMock,
        mock_gh: MagicMock,
        _: MagicMock,
    ) -> None:
        """Basic PR creation without auto-merge."""
        mock_git.return_value = _ok()  # rev-parse
        mock_gh.return_value = _ok(stdout=f"{_PR_URL}\n")

        result = GitPRTool().execute(
            title="feat: add worktree support",
            auto_merge=False,
            path="/repo",
        )
        assert result.success
        assert result.data["pr_url"] == _PR_URL
        assert result.data["pr_number"] == "42"
        assert result.data["auto_merge"] is False

        # Verify gh pr create args.
        create_call = mock_gh.call_args_list[0]
        args = create_call[0][0]
        assert args[:2] == ["pr", "create"]
        assert "--title" in args
        assert "feat: add worktree support" in args

    @patch("axm_git.tools.pr.gh_available", return_value=True)
    @patch("axm_git.tools.pr.run_gh")
    @patch("axm_git.tools.pr.run_git")
    def test_pr_create_with_auto_merge(
        self,
        mock_git: MagicMock,
        mock_gh: MagicMock,
        _: MagicMock,
    ) -> None:
        """Auto-merge calls gh pr merge --auto --squash."""
        mock_git.return_value = _ok()  # rev-parse
        mock_gh.side_effect = [
            _ok(stdout=f"{_PR_URL}\n"),  # pr create
            _ok(),  # pr merge --auto --squash
        ]

        result = GitPRTool().execute(
            title="feat: add worktree support",
            auto_merge=True,
            path="/repo",
        )
        assert result.success
        assert result.data["auto_merge"] is True
        assert result.data["pr_number"] == "42"

        # Verify merge call.
        merge_call = mock_gh.call_args_list[1]
        args = merge_call[0][0]
        assert args == ["pr", "merge", "42", "--auto", "--squash"]

    @patch("axm_git.tools.pr.gh_available", return_value=False)
    @patch("axm_git.tools.pr.run_git")
    def test_pr_no_gh(
        self,
        mock_git: MagicMock,
        _: MagicMock,
    ) -> None:
        """Missing gh CLI returns failure."""
        mock_git.return_value = _ok()  # rev-parse

        result = GitPRTool().execute(
            title="feat: anything",
            path="/repo",
        )
        assert not result.success
        assert result.error == "gh CLI not available"

    @patch("axm_git.tools.pr.run_git")
    def test_not_git_repo(self, mock_git: MagicMock) -> None:
        """Non-git directory returns failure."""
        mock_git.return_value = _fail(stderr="fatal: not a git repository")

        with patch("axm_git.tools.pr.not_a_repo_error") as mock_err:
            mock_err.return_value = MagicMock(success=False, error="not a repo")
            result = GitPRTool().execute(
                title="feat: anything",
                path="/not-a-repo",
            )
            assert not result.success
            mock_err.assert_called_once()

    @patch("axm_git.tools.pr.gh_available", return_value=True)
    @patch("axm_git.tools.pr.run_gh")
    @patch("axm_git.tools.pr.run_git")
    def test_pr_create_with_body(
        self,
        mock_git: MagicMock,
        mock_gh: MagicMock,
        _: MagicMock,
    ) -> None:
        """Body is passed to gh pr create."""
        mock_git.return_value = _ok()
        mock_gh.return_value = _ok(stdout=f"{_PR_URL}\n")

        GitPRTool().execute(
            title="feat: x",
            body="Detailed description",
            auto_merge=False,
            path="/repo",
        )

        create_call = mock_gh.call_args_list[0]
        args = create_call[0][0]
        assert "--body" in args
        assert "Detailed description" in args

    @patch("axm_git.tools.pr.gh_available", return_value=True)
    @patch("axm_git.tools.pr.run_gh")
    @patch("axm_git.tools.pr.run_git")
    def test_pr_create_failure(
        self,
        mock_git: MagicMock,
        mock_gh: MagicMock,
        _: MagicMock,
    ) -> None:
        """gh pr create failure is surfaced."""
        mock_git.return_value = _ok()
        mock_gh.return_value = _fail(stderr="pull request already exists")

        result = GitPRTool().execute(
            title="feat: x",
            path="/repo",
        )
        assert not result.success
        assert "already exists" in (result.error or "")
