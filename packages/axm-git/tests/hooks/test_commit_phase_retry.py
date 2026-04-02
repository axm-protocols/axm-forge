from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pytest_mock import MockerFixture

from axm_git.hooks.commit_phase import _retry_commit_on_autofix


def _git_result(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> SimpleNamespace:
    """Build a minimal GitResult-like object."""
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


# ---------- Unit tests ----------


class TestRetryCommitOnAutofix:
    """Tests for the extracted _retry_commit_on_autofix helper."""

    def test_commit_retry_on_autofix(
        self, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        """First commit fails with 'files were modified', retry succeeds."""
        files = ["src/foo.py", "src/bar.py"]
        cmd = ["commit", "-m", "feat: add stuff", "--no-verify"]
        git_root = tmp_path

        fail_result = _git_result(1, stderr="files were modified by pre-commit hook")
        ok_result = _git_result(0, stdout="[main abc1234] feat: add stuff")

        mock_run_git = mocker.patch(
            "axm_git.hooks.commit_phase.run_git",
            side_effect=[ok_result],  # only the retry call goes through run_git here
        )
        mock_stage = mocker.patch(
            "axm_git.hooks.commit_phase._stage_spec_files",
            return_value=None,  # no error
        )

        result = _retry_commit_on_autofix(
            files=files, cmd=cmd, git_root=git_root, first_result=fail_result
        )

        # _stage_spec_files called to re-stage
        mock_stage.assert_called_once_with(files, git_root)
        # run_git called for the retry commit
        mock_run_git.assert_called_once_with(cmd, git_root)
        # Final result is the successful retry
        assert result.returncode == 0

    def test_commit_retry_still_fails(
        self, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        """First commit fails with 'files were modified', retry also fails."""
        files = ["src/foo.py"]
        cmd = ["commit", "-m", "fix: thing"]
        git_root = tmp_path

        fail_result = _git_result(1, stderr="files were modified by pre-commit hook")
        retry_fail = _git_result(1, stderr="some other git error on retry")

        mocker.patch(
            "axm_git.hooks.commit_phase.run_git",
            return_value=retry_fail,
        )
        mocker.patch(
            "axm_git.hooks.commit_phase._stage_spec_files",
            return_value=None,
        )

        result = _retry_commit_on_autofix(
            files=files, cmd=cmd, git_root=git_root, first_result=fail_result
        )

        # Should return the failed retry result
        assert result.returncode != 0
        assert "some other git error" in result.stderr


# ---------- Edge cases ----------


class TestRetryEdgeCases:
    """Edge cases for retry logic."""

    def test_no_retry_needed_returns_first_result(
        self, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        """When first_result has no 'files were modified', return it unchanged."""
        files = ["src/foo.py"]
        cmd = ["commit", "-m", "chore: cleanup"]
        git_root = tmp_path

        # A failure that is NOT an autofix scenario
        fail_result = _git_result(1, stderr="fatal: not a git repository")

        mock_run_git = mocker.patch("axm_git.hooks.commit_phase.run_git")
        mock_stage = mocker.patch("axm_git.hooks.commit_phase._stage_spec_files")

        result = _retry_commit_on_autofix(
            files=files, cmd=cmd, git_root=git_root, first_result=fail_result
        )

        # No retry attempted
        mock_run_git.assert_not_called()
        mock_stage.assert_not_called()
        # Returns the original failure
        assert result.returncode == 1
        assert result.stderr == "fatal: not a git repository"

    def test_autofix_restage_error_returns_restage_failure(
        self, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        """Autofix detected but re-staging fails -> return error result."""
        files = ["src/foo.py"]
        cmd = ["commit", "-m", "feat: thing"]
        git_root = tmp_path

        fail_result = _git_result(1, stderr="files were modified by pre-commit hook")

        mocker.patch("axm_git.hooks.commit_phase.run_git")
        mocker.patch(
            "axm_git.hooks.commit_phase._stage_spec_files",
            return_value="git add failed for src/foo.py: permission denied",
        )

        result = _retry_commit_on_autofix(
            files=files, cmd=cmd, git_root=git_root, first_result=fail_result
        )

        # Should propagate the staging error
        assert result.returncode != 0
        assert "git add failed" in result.stderr
