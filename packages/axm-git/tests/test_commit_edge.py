from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from axm_git.tools.commit import GitCommitTool

MODULE = "axm_git.tools.commit"


def _git_result(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


# ---------------------------------------------------------------------------
# Edge case: empty commit list
# ---------------------------------------------------------------------------


class TestEmptyCommitList:
    """commits=[] returns success=False with clear error."""

    def test_empty_list(self) -> None:
        tool = GitCommitTool()
        result = tool.execute(path="/tmp/repo", commits=[])

        assert result.success is False
        assert result.error == "No commits provided"

    def test_none_defaults_to_empty(self) -> None:
        tool = GitCommitTool()
        result = tool.execute(path="/tmp/repo", commits=None)

        assert result.success is False
        assert result.error == "No commits provided"


# ---------------------------------------------------------------------------
# Edge case: mid-batch failure
# ---------------------------------------------------------------------------


class TestMidBatchFailure:
    """Commit 2/3 fails pre-commit → failure with succeeded=1, partial results."""

    @pytest.fixture()
    def three_commits(self) -> list[dict[str, Any]]:
        return [
            {"files": ["a.py"], "message": "first commit"},
            {"files": ["b.py"], "message": "second commit"},
            {"files": ["c.py"], "message": "third commit"},
        ]

    @patch(f"{MODULE}.author_args", return_value=[])
    @patch(f"{MODULE}.resolve_identity", return_value=None)
    @patch(f"{MODULE}.run_git")
    def test_mid_batch_precommit_failure(
        self,
        mock_run_git: MagicMock,
        _mock_identity: MagicMock,
        _mock_args: MagicMock,
        tmp_path: Path,
        three_commits: list[dict[str, Any]],
    ) -> None:
        mock_run_git.side_effect = [
            # rev-parse --git-dir  (repo check)
            _git_result(0),
            # Commit 1: git add -A
            _git_result(0),
            # Commit 1: git commit
            _git_result(0, stdout="[main abc1234] first commit\n"),
            # Commit 1: git log -1 (SHA)
            _git_result(0, stdout="abc1234abcdef1234567890\n"),
            # Commit 2: git add -A
            _git_result(0),
            # Commit 2: git commit (pre-commit fails)
            _git_result(1, stderr="pre-commit hook failed"),
        ]

        tool = GitCommitTool()
        result = tool.execute(path=str(tmp_path), commits=three_commits)

        assert result.success is False
        assert result.error is not None
        assert "Commit 2" in result.error
        assert "pre-commit failed" in result.error
        assert result.data["succeeded"] == 1
        assert len(result.data["results"]) == 1
        assert result.data["results"][0]["message"] == "first commit"
        assert result.data["results"][0]["sha"] == "abc1234"
        # Third commit should never have been attempted
        assert mock_run_git.call_count == 6

    @patch(f"{MODULE}.author_args", return_value=[])
    @patch(f"{MODULE}.resolve_identity", return_value=None)
    @patch(f"{MODULE}.run_git")
    def test_mid_batch_failure_includes_failed_commit_details(
        self,
        mock_run_git: MagicMock,
        _mock_identity: MagicMock,
        _mock_args: MagicMock,
        tmp_path: Path,
        three_commits: list[dict[str, Any]],
    ) -> None:
        mock_run_git.side_effect = [
            _git_result(0),  # rev-parse
            _git_result(0),  # add commit 1
            _git_result(0, stdout="[main aaa] first\n"),  # commit 1
            _git_result(0, stdout="aaaaaaa\n"),  # log commit 1
            _git_result(0),  # add commit 2
            _git_result(1, stderr="hook error output"),  # commit 2 fails
        ]

        tool = GitCommitTool()
        result = tool.execute(path=str(tmp_path), commits=three_commits)

        failed = result.data["failed_commit"]
        assert failed["index"] == 2
        assert failed["message"] == "second commit"
        assert failed["retried"] is False
