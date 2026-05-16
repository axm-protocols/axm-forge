"""Split from ``test_commit_phase.py`` — CommitPhaseHook x run_git scenarios."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_mock import MockerFixture

from axm_git.hooks.commit_phase import CommitPhaseHook

pytestmark = pytest.mark.integration


# --- Tests from test_commit_phase_retry.py (commit retry / autofix, AXM-899) ---


def _cp(
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    """Build a fake CompletedProcess."""
    return subprocess.CompletedProcess(
        args=["git"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


class TestCommitRetryAfterAutofix:
    """Retry logic when pre-commit hooks auto-fix files."""

    @pytest.fixture
    def hook(self) -> CommitPhaseHook:
        return CommitPhaseHook()

    @pytest.fixture
    def context(self, tmp_path: Path) -> dict[str, Any]:
        """Minimal from_outputs context with a commit_spec."""
        return {
            "working_dir": str(tmp_path),
            "commit_spec": {
                "message": "feat(git): retry test",
                "files": ["src/foo.py"],
            },
        }

    def test_commit_retries_after_autofix(
        self,
        hook: CommitPhaseHook,
        context: dict[str, Any],
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        """When commit fails with 'files were modified', re-stage and retry."""
        mock_stage = mocker.patch(
            "axm_git.hooks.commit_phase._stage_spec_files",
            return_value=None,
        )
        mocker.patch(
            "axm_git.hooks.commit_phase.find_git_root",
            return_value=tmp_path,
        )

        # run_git calls:
        #   1. diff --cached (check staged) -> has staged files
        #   2. commit -> rc=1 "files were modified by formatter"
        #   3. commit retry -> rc=0
        #   4. rev-parse -> short hash
        mocker.patch(
            "axm_git.hooks.commit_phase.run_git",
            side_effect=[
                _cp(stdout="src/foo.py\n"),
                _cp(
                    returncode=1,
                    stderr="files were modified by formatter",
                ),
                _cp(returncode=0),
                _cp(stdout="abc1234\n"),
            ],
        )

        result = hook.execute(context, from_outputs=True)

        assert result.success
        assert result.metadata["commit"] == "abc1234"
        # _stage_spec_files called twice: initial + re-stage after autofix
        assert mock_stage.call_count == 2

    def test_commit_retry_fails(
        self,
        hook: CommitPhaseHook,
        context: dict[str, Any],
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        """When commit fails twice, return HookResult.fail()."""
        mocker.patch(
            "axm_git.hooks.commit_phase._stage_spec_files",
            return_value=None,
        )
        mocker.patch(
            "axm_git.hooks.commit_phase.find_git_root",
            return_value=tmp_path,
        )

        mocker.patch(
            "axm_git.hooks.commit_phase.run_git",
            side_effect=[
                _cp(stdout="src/foo.py\n"),
                _cp(
                    returncode=1,
                    stderr="files were modified by formatter",
                ),
                _cp(returncode=1, stderr="pre-commit hook failed"),
            ],
        )

        result = hook.execute(context, from_outputs=True)

        assert not result.success
        assert "commit failed" in (result.error or "").lower()

    def test_commit_clean_no_retry(
        self,
        hook: CommitPhaseHook,
        context: dict[str, Any],
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        """When commit succeeds first time, no retry occurs."""
        mock_stage = mocker.patch(
            "axm_git.hooks.commit_phase._stage_spec_files",
            return_value=None,
        )
        mocker.patch(
            "axm_git.hooks.commit_phase.find_git_root",
            return_value=tmp_path,
        )

        mocker.patch(
            "axm_git.hooks.commit_phase.run_git",
            side_effect=[
                _cp(stdout="src/foo.py\n"),  # diff --cached
                _cp(returncode=0),  # commit succeeds
                _cp(stdout="def5678\n"),  # rev-parse
            ],
        )

        result = hook.execute(context, from_outputs=True)

        assert result.success
        assert result.metadata["commit"] == "def5678"
        # _stage_spec_files called only once (no retry)
        assert mock_stage.call_count == 1


# --- Tests from test_commit_phase_skip_hooks.py (skip_hooks parameter) ---


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
        """By default (skip_hooks=False), git commit args do NOT include --no-verify."""
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
        assert "--no-verify" not in commit_calls[0][0][0]

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
