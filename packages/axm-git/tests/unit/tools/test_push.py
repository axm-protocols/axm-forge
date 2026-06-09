"""Unit tests for GitPushTool."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from axm_git.tools.push import GitPushTool


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


class TestGitPushTool:
    """Test GitPushTool behavior."""

    def test_name(self) -> None:
        assert GitPushTool().name == "git_push"

    @patch("axm_git.tools.push.run_git")
    def test_push_clean(self, mock_git: MagicMock) -> None:
        """Clean tree pushes successfully."""
        mock_git.side_effect = [
            _ok(),  # rev-parse --git-dir
            _ok(stdout=""),  # status --porcelain (clean)
            _ok(stdout="main\n"),  # branch --show-current
            _ok(stdout="origin/main"),  # rev-parse @{u} (has upstream)
            _ok(stderr="Everything up-to-date"),  # push
        ]
        result = GitPushTool().execute(path="/repo")
        assert result.success
        assert result.data["branch"] == "main"
        assert result.data["pushed"] is True
        assert result.data["set_upstream"] is False

        # Verify push command.
        push_call = mock_git.call_args_list[4]
        assert push_call[0][0] == ["push", "origin", "main"]

    @patch("axm_git.tools.push.run_git")
    def test_push_dirty_refuses(self, mock_git: MagicMock) -> None:
        """Dirty tree is rejected with file list (``-z`` NUL fixtures)."""
        mock_git.side_effect = [
            _ok(),  # rev-parse
            _ok(stdout=" M README.md\x00?? new.py\x00"),  # dirty (status -z)
        ]
        result = GitPushTool().execute(path="/repo")
        assert not result.success
        assert "dirty" in (result.error or "").lower()
        assert "README.md" in result.data["dirty_files"]
        assert "new.py" in result.data["dirty_files"]

    @patch("axm_git.tools.push.run_git")
    def test_dirty_check_rename_via_z(self, mock_git: MagicMock) -> None:
        """AC1,AC3: a rename in the dirty check lists the new path only."""
        mock_git.side_effect = [
            _ok(),  # rev-parse
            _ok(stdout="R  new.py\x00old.py\x00"),  # rename (status -z)
        ]
        result = GitPushTool().execute(path="/repo")
        assert not result.success
        dirty = result.data["dirty_files"]
        assert "new.py" in dirty
        assert "old.py" not in dirty
        assert "->" not in " ".join(dirty)

    @patch("axm_git.tools.push.run_git")
    def test_push_set_upstream(self, mock_git: MagicMock) -> None:
        """New branch auto-sets upstream."""
        mock_git.side_effect = [
            _ok(),  # rev-parse
            _ok(stdout=""),  # clean
            _ok(stdout="feat/x\n"),  # branch
            _fail(stderr="no upstream"),  # no upstream
            _ok(),  # push --set-upstream
        ]
        result = GitPushTool().execute(path="/repo")
        assert result.success
        assert result.data["set_upstream"] is True

        push_call = mock_git.call_args_list[4]
        args = push_call[0][0]
        assert "--set-upstream" in args
        assert args == ["push", "--set-upstream", "origin", "feat/x"]

    @patch("axm_git.tools.push.run_git")
    def test_push_custom_remote(self, mock_git: MagicMock) -> None:
        """Custom remote is used in push command."""
        mock_git.side_effect = [
            _ok(),  # rev-parse
            _ok(stdout=""),  # clean
            _ok(stdout="main\n"),  # branch
            _ok(stdout="upstream/main"),  # has upstream
            _ok(),  # push
        ]
        result = GitPushTool().execute(
            path="/repo",
            remote="upstream",
        )
        assert result.success
        assert result.data["remote"] == "upstream"

        push_call = mock_git.call_args_list[4]
        assert push_call[0][0] == ["push", "upstream", "main"]

    @pytest.mark.parametrize(
        ("kwargs", "present", "absent", "expected_args"),
        [
            pytest.param(
                {"force": True},
                "--force-with-lease",
                "--force",
                ["push", "--force-with-lease", "origin", "main"],
                id="force_uses_lease",
            ),
            pytest.param(
                {"force": True, "force_unconditional": True},
                "--force",
                "--force-with-lease",
                ["push", "--force", "origin", "main"],
                id="unconditional_uses_bare_force",
            ),
        ],
    )
    @patch("axm_git.tools.push.run_git")
    def test_force_flag_selection(
        self,
        mock_git: MagicMock,
        kwargs: dict[str, bool],
        present: str,
        absent: str,
        expected_args: list[str],
    ) -> None:
        """AC1, AC2: force=True uses lease; unconditional uses bare force."""
        mock_git.side_effect = [
            _ok(),  # rev-parse
            _ok(stdout=""),  # clean
            _ok(stdout="main\n"),  # branch
            _ok(stdout="origin/main"),  # has upstream
            _ok(),  # push
        ]
        result = GitPushTool().execute(path="/repo", **kwargs)
        assert result.success

        push_call = mock_git.call_args_list[4]
        args = push_call[0][0]
        assert present in args
        assert absent not in args
        assert args == expected_args

    @patch("axm_git.tools.push.run_git")
    def test_non_force_push_has_no_force_flag(self, mock_git: MagicMock) -> None:
        """AC3: force=False emits neither --force nor --force-with-lease."""
        mock_git.side_effect = [
            _ok(),  # rev-parse
            _ok(stdout=""),  # clean
            _ok(stdout="main\n"),  # branch
            _ok(stdout="origin/main"),  # has upstream
            _ok(),  # push
        ]
        result = GitPushTool().execute(path="/repo", force=False)
        assert result.success

        push_call = mock_git.call_args_list[4]
        args = push_call[0][0]
        assert "--force" not in args
        assert "--force-with-lease" not in args
        assert args == ["push", "origin", "main"]

    @patch("axm_git.tools.push.run_git")
    def test_force_true_backward_compatible(self, mock_git: MagicMock) -> None:
        """AC4: existing force=True call (no new flag) applies lease, no error."""
        mock_git.side_effect = [
            _ok(),  # rev-parse
            _ok(stdout=""),  # clean
            _ok(stdout="main\n"),  # branch
            _ok(stdout="origin/main"),  # has upstream
            _ok(),  # push --force-with-lease
        ]
        result = GitPushTool().execute(path="/repo", force=True)
        assert result.success

        push_call = mock_git.call_args_list[4]
        args = push_call[0][0]
        assert "--force-with-lease" in args

    @patch("axm_git.tools.push.run_git")
    def test_not_git_repo(self, mock_git: MagicMock) -> None:
        """Non-git directory returns failure."""
        mock_git.side_effect = [
            _fail(stderr="fatal: not a git repository"),
        ]
        with patch("axm_git.tools.push.not_a_repo_error") as mock_err:
            mock_err.return_value = MagicMock(
                success=False,
                error="not a repo",
            )
            result = GitPushTool().execute(path="/not-a-repo")
            assert not result.success
            mock_err.assert_called_once()

    @patch("axm_git.tools.push.run_git")
    def test_detached_head(self, mock_git: MagicMock) -> None:
        """Detached HEAD returns failure."""
        mock_git.side_effect = [
            _ok(),  # rev-parse
            _ok(stdout=""),  # clean
            _ok(stdout="\n"),  # no branch (detached)
        ]
        result = GitPushTool().execute(path="/repo")
        assert not result.success
        assert "detached" in (result.error or "").lower()

    @patch("axm_git.tools.push.run_git")
    def test_push_failure_relayed(self, mock_git: MagicMock) -> None:
        """Push failure error is relayed."""
        mock_git.side_effect = [
            _ok(),  # rev-parse
            _ok(stdout=""),  # clean
            _ok(stdout="main\n"),  # branch
            _ok(stdout="origin/main"),  # upstream
            _fail(stderr="fatal: remote 'nonexistent' does not exist"),
        ]
        result = GitPushTool().execute(
            path="/repo",
            remote="nonexistent",
        )
        assert not result.success
        assert "does not exist" in (result.error or "")
