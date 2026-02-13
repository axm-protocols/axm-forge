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
                    return _fail(stderr="mypy error")
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
            ],
        )
        assert not result.success
        assert result.data["succeeded"] == 1
        assert result.data["failed_commit"]["index"] == 2

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

    # ── Bug fix tests ──────────────────────────────────────────────

    @patch("axm_git.tools.commit.run_git")
    def test_git_add_uses_dash_a_flag(self, mock_git: MagicMock) -> None:
        """git add call includes -A and -- flags."""
        add_calls: list[list[str]] = []

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "add":
                add_calls.append(args)
                return _ok()
            if args[0] == "commit":
                return _ok()
            if args[0] == "log":
                return _ok("abc1234")
            return _ok()

        mock_git.side_effect = _side_effect
        GitCommitTool().execute(
            path="/tmp/test",
            commits=[{"files": ["a.py"], "message": "fix: a"}],
        )
        assert len(add_calls) == 1
        assert "-A" in add_calls[0]
        assert "--" in add_calls[0]

    @patch("axm_git.tools.commit.run_git")
    def test_auto_retry_on_ruff_fix(self, mock_git: MagicMock) -> None:
        """When pre-commit auto-fixes, re-stage and retry once."""
        commit_count = 0

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            nonlocal commit_count
            if args[0] == "add":
                return _ok()
            if args[0] == "commit":
                commit_count += 1
                if commit_count == 1:
                    return _fail(stdout="files were modified by this hook")
                return _ok()  # retry succeeds
            if args[0] == "log":
                return _ok("abc1234")
            return _ok()

        mock_git.side_effect = _side_effect
        result = GitCommitTool().execute(
            path="/tmp/test",
            commits=[{"files": ["a.py"], "message": "fix: a"}],
        )
        assert result.success
        assert result.data["results"][0]["retried"] is True
        assert commit_count == 2

    @patch("axm_git.tools.commit.run_git")
    def test_auto_retry_fails_twice(self, mock_git: MagicMock) -> None:
        """When retry also fails, report error with retried=True."""

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "add":
                return _ok()
            if args[0] == "commit":
                return _fail(stdout="files were modified by this hook")
            if args[0] == "diff":
                return _ok("a.py\n")
            return _ok()

        mock_git.side_effect = _side_effect
        result = GitCommitTool().execute(
            path="/tmp/test",
            commits=[{"files": ["a.py"], "message": "fix: a"}],
        )
        assert not result.success
        assert result.data["failed_commit"]["retried"] is True
        assert "a.py" in result.data["failed_commit"]["auto_fixed_files"]
