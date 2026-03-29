"""Tests for commit retry after pre-commit auto-fix (AXM-899)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from pytest_mock import MockerFixture

from axm_git.hooks.commit_phase import CommitPhaseHook


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
