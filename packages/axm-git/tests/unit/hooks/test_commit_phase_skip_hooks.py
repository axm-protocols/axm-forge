"""Tests for skip_hooks parameter in CommitPhaseHook."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from axm_git.hooks.commit_phase import CommitPhaseHook


def _ok(stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["git"],
        returncode=0,
        stdout=stdout,
        stderr=stderr,
    )


class TestCommitFromOutputsSkipHooks:
    """Tests for skip_hooks behaviour in _commit_from_outputs."""

    @patch("axm_git.hooks.commit_phase.run_git")
    @patch("axm_git.hooks.commit_phase.find_git_root")
    def test_commit_from_outputs_skip_hooks_default(
        self,
        mock_find_root: MagicMock,
        mock_run_git: MagicMock,
        tmp_path: Path,
    ) -> None:
        """By default, git commit args include --no-verify."""
        mock_find_root.return_value = tmp_path
        (tmp_path / "f.py").write_text("x")

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "add":
                return _ok()
            if args[0] == "diff":
                return _ok(stdout="f.py\n")
            if args[0] == "commit":
                return _ok()
            if args[0] == "rev-parse":
                return _ok(stdout="abc1234")
            return _ok()

        mock_run_git.side_effect = _side_effect

        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_path),
                "commit_spec": {
                    "message": "feat: test",
                    "files": ["f.py"],
                },
            },
            from_outputs=True,
        )

        assert result.success
        # Find the commit call and verify --no-verify is present
        commit_calls = [
            call for call in mock_run_git.call_args_list if call[0][0][0] == "commit"
        ]
        assert len(commit_calls) == 1
        assert "--no-verify" in commit_calls[0][0][0]

    @patch("axm_git.hooks.commit_phase.run_git")
    @patch("axm_git.hooks.commit_phase.find_git_root")
    def test_commit_from_outputs_skip_hooks_false(
        self,
        mock_find_root: MagicMock,
        mock_run_git: MagicMock,
        tmp_path: Path,
    ) -> None:
        """When skip_hooks=False, git commit does NOT include --no-verify."""
        mock_find_root.return_value = tmp_path
        (tmp_path / "f.py").write_text("x")

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "add":
                return _ok()
            if args[0] == "diff":
                return _ok(stdout="f.py\n")
            if args[0] == "commit":
                return _ok()
            if args[0] == "rev-parse":
                return _ok(stdout="abc1234")
            return _ok()

        mock_run_git.side_effect = _side_effect

        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_path),
                "commit_spec": {
                    "message": "feat: test",
                    "files": ["f.py"],
                },
            },
            from_outputs=True,
            skip_hooks=False,
        )

        assert result.success
        commit_calls = [
            call for call in mock_run_git.call_args_list if call[0][0][0] == "commit"
        ]
        assert len(commit_calls) == 1
        assert "--no-verify" not in commit_calls[0][0][0]

    @patch("axm_git.hooks.commit_phase.run_git")
    @patch("axm_git.hooks.commit_phase.find_git_root")
    def test_execute_passes_skip_hooks_param(
        self,
        mock_find_root: MagicMock,
        mock_run_git: MagicMock,
        tmp_path: Path,
    ) -> None:
        """execute() threads skip_hooks from params to _commit_from_outputs."""
        mock_find_root.return_value = tmp_path
        (tmp_path / "f.py").write_text("x")

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "add":
                return _ok()
            if args[0] == "diff":
                return _ok(stdout="f.py\n")
            if args[0] == "commit":
                return _ok()
            if args[0] == "rev-parse":
                return _ok(stdout="abc1234")
            return _ok()

        mock_run_git.side_effect = _side_effect

        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_path),
                "commit_spec": {
                    "message": "feat: test",
                    "files": ["f.py"],
                },
            },
            from_outputs=True,
            skip_hooks=True,
        )

        assert result.success
        commit_calls = [
            call for call in mock_run_git.call_args_list if call[0][0][0] == "commit"
        ]
        assert len(commit_calls) == 1
        assert "--no-verify" in commit_calls[0][0][0]


class TestCommitToolNoSkip:
    """Verify CommitTool (MCP) does NOT use --no-verify."""

    @patch("axm_git.tools.commit.run_git")
    def test_commit_tool_no_skip(self, mock_git: MagicMock) -> None:
        """CommitTool.execute does NOT include --no-verify."""
        from axm_git.tools.commit import GitCommitTool

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
        commit_calls = [
            call for call in mock_git.call_args_list if call[0][0][0] == "commit"
        ]
        assert len(commit_calls) == 1
        assert "--no-verify" not in commit_calls[0][0][0]
