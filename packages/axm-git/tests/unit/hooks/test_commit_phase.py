"""Unit tests for axm_git.hooks.commit_phase (no real I/O)."""

from __future__ import annotations

import inspect
import subprocess
from typing import Any
from unittest.mock import MagicMock, patch

from axm_git.hooks.commit_phase import CommitPhaseHook, _build_commit_cmd


def _ok(stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["git"],
        returncode=0,
        stdout=stdout,
        stderr=stderr,
    )


class TestBuildCommitCmd:
    """Unit-scope tests for _build_commit_cmd (no I/O)."""

    def test_build_commit_cmd_no_verify_omitted_when_skip_hooks_false(self) -> None:
        cmd = _build_commit_cmd("msg", None, skip_hooks=False)
        assert "--no-verify" not in cmd

    def test_build_commit_cmd_no_verify_present_when_skip_hooks_true(self) -> None:
        cmd = _build_commit_cmd("msg", None, skip_hooks=True)
        assert "--no-verify" in cmd

    def test_commit_phase_default_skip_hooks_is_false(self) -> None:
        sig = inspect.signature(CommitPhaseHook._commit_from_outputs)
        assert sig.parameters["skip_hooks"].default is False


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
