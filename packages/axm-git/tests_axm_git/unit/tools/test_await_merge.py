"""Unit tests for GitAwaitMergeTool."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from axm_git.tools.await_merge import GitAwaitMergeTool


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


class TestGitAwaitMergeTool:
    """Test GitAwaitMergeTool behavior (immediate-termination cases only)."""

    def test_name(self) -> None:
        """Tool registers under the git_await_merge name."""
        assert GitAwaitMergeTool().name == "git_await_merge"

    @patch("axm_git.tools.await_merge.run_gh")
    @patch("axm_git.tools.await_merge.gh_available")
    def test_merged_immediately(
        self, mock_avail: MagicMock, mock_gh: MagicMock
    ) -> None:
        """A PR already in the MERGED state returns success on first poll."""
        mock_avail.return_value = True
        mock_gh.return_value = _ok(stdout='{"state": "MERGED"}')
        result = GitAwaitMergeTool().execute(pr="42", path="/repo")
        assert result.success
        assert result.data["merged"] is True
        assert result.data["pr_ref"] == "42"

    @patch("axm_git.tools.await_merge.run_gh")
    @patch("axm_git.tools.await_merge.gh_available")
    def test_closed_without_merge(
        self, mock_avail: MagicMock, mock_gh: MagicMock
    ) -> None:
        """A CLOSED PR returns failure mentioning it was closed."""
        mock_avail.return_value = True
        mock_gh.return_value = _ok(stdout='{"state": "CLOSED"}')
        result = GitAwaitMergeTool().execute(pr="42", path="/repo")
        assert not result.success
        assert "closed" in (result.error or "")

    @patch("axm_git.tools.await_merge.run_gh")
    @patch("axm_git.tools.await_merge.gh_available")
    def test_gh_unavailable(self, mock_avail: MagicMock, mock_gh: MagicMock) -> None:
        """An unavailable gh CLI returns failure without polling."""
        mock_avail.return_value = False
        result = GitAwaitMergeTool().execute(pr="42", path="/repo")
        assert not result.success
        assert "gh CLI not available" in (result.error or "")
        mock_gh.assert_not_called()

    @patch("axm_git.tools.await_merge.run_gh")
    @patch("axm_git.tools.await_merge.gh_available")
    def test_query_fails(self, mock_avail: MagicMock, mock_gh: MagicMock) -> None:
        """A non-zero gh query returns failure on the first poll."""
        mock_avail.return_value = True
        mock_gh.return_value = _fail(stderr="could not resolve to a PullRequest")
        result = GitAwaitMergeTool().execute(pr="42", path="/repo")
        assert not result.success
        assert "failed to query PR 42 state" in (result.error or "")
