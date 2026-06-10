"""Unit tests for GitMergeTool."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from axm_git.tools.merge import GitMergeTool


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


class TestGitMergeTool:
    """Test GitMergeTool behavior."""

    def test_name(self) -> None:
        """Tool registers under the git_merge name."""
        assert GitMergeTool().name == "git_merge"

    @patch("axm_git.tools.merge.resolve_identity")
    @patch("axm_git.tools.merge.run_git")
    def test_squash_merge_success(
        self, mock_git: MagicMock, mock_identity: MagicMock
    ) -> None:
        """Squash-merge a branch into the default target and commit."""
        mock_identity.return_value = None
        mock_git.side_effect = [
            _ok(),  # rev-parse --git-dir
            _ok(stderr="Switched to branch 'main'"),  # checkout main
            _ok(stdout="Squash commit -- not updating HEAD"),  # merge --squash
            _ok(stdout="[main abc123] Merge feat/x (squash)"),  # commit
        ]
        result = GitMergeTool().execute(branch="feat/x", path="/repo")
        assert result.success
        assert result.data["merged"] == "feat/x"
        assert result.data["into"] == "main"
        assert result.data["message"] == "Merge feat/x (squash)"

    @patch("axm_git.tools.merge.resolve_identity")
    @patch("axm_git.tools.merge.run_git")
    def test_merge_squash_in_call_args(
        self, mock_git: MagicMock, mock_identity: MagicMock
    ) -> None:
        """The merge step issues ``merge --squash <branch>``."""
        mock_identity.return_value = None
        mock_git.side_effect = [
            _ok(),  # rev-parse
            _ok(),  # checkout
            _ok(),  # merge --squash
            _ok(),  # commit
        ]
        GitMergeTool().execute(branch="feat/x", path="/repo")

        merge_call = mock_git.call_args_list[2]
        assert merge_call[0][0] == ["merge", "--squash", "feat/x"]

    @patch("axm_git.tools.merge.resolve_identity")
    @patch("axm_git.tools.merge.run_git")
    def test_custom_target_and_message(
        self, mock_git: MagicMock, mock_identity: MagicMock
    ) -> None:
        """A custom target branch and message are honoured."""
        mock_identity.return_value = None
        mock_git.side_effect = [_ok(), _ok(), _ok(), _ok()]
        result = GitMergeTool().execute(
            branch="feat/x",
            target_branch="develop",
            message="custom msg",
            path="/repo",
        )
        assert result.success
        assert result.data["into"] == "develop"
        assert result.data["message"] == "custom msg"

        checkout_call = mock_git.call_args_list[1]
        assert checkout_call[0][0] == ["checkout", "develop"]

    @patch("axm_git.tools.merge.resolve_identity")
    @patch("axm_git.tools.merge.run_git")
    def test_identity_passed_to_commit(
        self, mock_git: MagicMock, mock_identity: MagicMock
    ) -> None:
        """A resolved identity flows into the commit ``--author`` args."""
        identity = MagicMock()
        identity.name = "Alice"
        identity.email = "alice@example.com"
        mock_identity.return_value = identity
        mock_git.side_effect = [_ok(), _ok(), _ok(), _ok()]
        result = GitMergeTool().execute(branch="feat/x", path="/repo")
        assert result.success

        commit_call = mock_git.call_args_list[3][0][0]
        assert "--author" in commit_call
        assert "Alice <alice@example.com>" in commit_call

    @patch("axm_git.tools.merge.resolve_identity")
    @patch("axm_git.tools.merge.run_git")
    def test_checkout_fails(
        self, mock_git: MagicMock, mock_identity: MagicMock
    ) -> None:
        """A failing target checkout returns failure."""
        mock_identity.return_value = None
        mock_git.side_effect = [
            _ok(),  # rev-parse
            _fail(stderr="error: pathspec 'main' did not match"),  # checkout
        ]
        result = GitMergeTool().execute(branch="feat/x", path="/repo")
        assert not result.success
        assert "checkout main failed" in (result.error or "")

    @patch("axm_git.tools.merge.resolve_identity")
    @patch("axm_git.tools.merge.run_git")
    def test_merge_fails(self, mock_git: MagicMock, mock_identity: MagicMock) -> None:
        """A failing squash merge returns failure."""
        mock_identity.return_value = None
        mock_git.side_effect = [
            _ok(),  # rev-parse
            _ok(),  # checkout
            _fail(stderr="CONFLICT (content): Merge conflict"),  # merge --squash
        ]
        result = GitMergeTool().execute(branch="feat/x", path="/repo")
        assert not result.success
        assert "merge --squash failed" in (result.error or "")

    @patch("axm_git.tools.merge.resolve_identity")
    @patch("axm_git.tools.merge.run_git")
    def test_commit_fails(self, mock_git: MagicMock, mock_identity: MagicMock) -> None:
        """A failing commit returns failure."""
        mock_identity.return_value = None
        mock_git.side_effect = [
            _ok(),  # rev-parse
            _ok(),  # checkout
            _ok(),  # merge --squash
            _fail(stdout="nothing to commit, working tree clean"),  # commit
        ]
        result = GitMergeTool().execute(branch="feat/x", path="/repo")
        assert not result.success
        assert "commit failed" in (result.error or "")

    @patch("axm_git.tools.merge.resolve_identity")
    @patch("axm_git.tools.merge.run_git")
    def test_not_git_repo(self, mock_git: MagicMock, mock_identity: MagicMock) -> None:
        """A non-git directory returns failure via not_a_repo_error."""
        mock_identity.return_value = None
        mock_git.side_effect = [
            _fail(stderr="fatal: not a git repository"),
        ]
        with patch("axm_git.tools.merge.not_a_repo_error") as mock_err:
            mock_err.return_value = MagicMock(
                success=False, error="not a repo", data=None
            )
            result = GitMergeTool().execute(branch="feat/x", path="/not-a-repo")
            assert not result.success
            mock_err.assert_called_once()
