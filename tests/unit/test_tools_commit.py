"""Unit tests for GitCommitTool."""

from __future__ import annotations

import subprocess
from typing import Any
from unittest.mock import MagicMock, patch

from axm_git.tools.commit import GitCommitTool


def _ok(stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["git"],
        returncode=0,
        stdout=stdout,
        stderr=stderr,
    )


def _fail(stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["git"],
        returncode=1,
        stdout=stdout,
        stderr=stderr,
    )


class TestGitCommitTool:
    """Test GitCommitTool behavior."""

    def test_name(self) -> None:
        tool = GitCommitTool()
        assert tool.name == "git_commit"

    def test_no_commits_provided(self) -> None:
        result = GitCommitTool().execute(path="/tmp/test", commits=[])
        assert not result.success
        assert "No commits" in (result.error or "")

    @patch("axm_git.tools.commit.run_git")
    def test_single_commit_success(self, mock_git: MagicMock) -> None:
        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "add":
                return _ok()
            if args[0] == "commit":
                return _ok()
            if args[0] == "log":
                return _ok("abc1234")
            return _ok()

        mock_git.side_effect = _side_effect
        result = GitCommitTool().execute(
            path="/tmp/test",
            commits=[{"files": ["src/foo.py"], "message": "fix: bug"}],
        )
        assert result.success
        assert result.data["total"] == 1
        assert result.data["results"][0]["sha"] == "abc1234"

    @patch("axm_git.tools.commit.run_git")
    def test_batch_commits(self, mock_git: MagicMock) -> None:
        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "add":
                return _ok()
            if args[0] == "commit":
                return _ok()
            if args[0] == "log":
                return _ok("abc1234")
            return _ok()

        mock_git.side_effect = _side_effect
        result = GitCommitTool().execute(
            path="/tmp/test",
            commits=[
                {"files": ["a.py"], "message": "fix: a"},
                {"files": ["b.py"], "message": "feat: b"},
                {"files": ["c.py"], "message": "docs: c"},
            ],
        )
        assert result.success
        assert result.data["total"] == 3
        assert result.data["succeeded"] == 3

    @patch("axm_git.tools.commit.run_git")
    def test_precommit_failure_stops_batch(self, mock_git: MagicMock) -> None:
        commit_count = 0

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            nonlocal commit_count
            if args[0] == "add":
                return _ok()
            if args[0] == "commit":
                commit_count += 1
                if commit_count == 2:
                    return _fail(
                        stdout="files were modified by this hook",
                        stderr="ruff failed",
                    )
                return _ok()
            if args[0] == "log":
                return _ok("abc1234")
            if args[0] == "diff":
                return _ok("src/b.py\n")
            return _ok()

        mock_git.side_effect = _side_effect
        result = GitCommitTool().execute(
            path="/tmp/test",
            commits=[
                {"files": ["a.py"], "message": "fix: a"},
                {"files": ["b.py"], "message": "feat: b"},
            ],
        )
        assert not result.success
        assert result.data["succeeded"] == 1
        assert result.data["failed_commit"]["index"] == 2
        assert "src/b.py" in result.data["failed_commit"]["auto_fixed_files"]

    def test_empty_files_error(self) -> None:
        result = GitCommitTool().execute(
            path="/tmp/test",
            commits=[{"files": [], "message": "fix: x"}],
        )
        assert not result.success
        assert "empty files" in (result.error or "")

    def test_empty_message_error(self) -> None:
        result = GitCommitTool().execute(
            path="/tmp/test",
            commits=[{"files": ["a.py"], "message": ""}],
        )
        assert not result.success
        assert "empty message" in (result.error or "")

    @patch("axm_git.tools.commit.run_git")
    def test_git_add_failure(self, mock_git: MagicMock) -> None:
        mock_git.return_value = _fail(stderr="pathspec 'x' did not match any files")
        result = GitCommitTool().execute(
            path="/tmp/test",
            commits=[{"files": ["x.py"], "message": "fix: x"}],
        )
        assert not result.success
        assert "git add failed" in (result.error or "")

    @patch("axm_git.tools.commit.run_git")
    def test_commit_with_body(self, mock_git: MagicMock) -> None:
        """Commit with body adds second -m flag."""

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "commit":
                assert "-m" in args
                # Should have two -m flags (message + body)
                m_count = args.count("-m")
                assert m_count == 2
                return _ok()
            if args[0] == "log":
                return _ok("abc1234")
            return _ok()

        mock_git.side_effect = _side_effect
        result = GitCommitTool().execute(
            path="/tmp/test",
            commits=[
                {
                    "files": ["a.py"],
                    "message": "feat: api",
                    "body": "Detailed explanation",
                }
            ],
        )
        assert result.success
