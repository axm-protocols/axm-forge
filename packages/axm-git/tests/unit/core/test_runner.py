"""Unit tests for axm_git.core.runner (no real I/O)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from axm_git.core import runner
from axm_git.core.runner import (
    find_git_root,
    gh_available,
    resolve_default_branch,
    run_gh,
    run_git,
)


class TestResolveDefaultBranch:
    """Unit tests for resolve_default_branch (run_git mocked)."""

    @patch("axm_git.core.runner.run_git")
    def test_resolve_default_branch_falls_back_to_main(
        self, mock_run_git: MagicMock
    ) -> None:
        """AC1: a non-zero symbolic-ref falls back to \"main\"."""
        mock_run_git.return_value = subprocess.CompletedProcess(
            args=["git"], returncode=1, stdout="", stderr="fatal: no origin/HEAD"
        )
        assert resolve_default_branch(Path("/repo")) == "main"

    @patch("axm_git.core.runner.run_git")
    def test_resolve_default_branch_parses_origin_head(
        self, mock_run_git: MagicMock
    ) -> None:
        """AC4: origin/HEAD -> master is parsed to \"master\"."""
        mock_run_git.return_value = subprocess.CompletedProcess(
            args=["git"],
            returncode=0,
            stdout="refs/remotes/origin/master\n",
            stderr="",
        )
        assert resolve_default_branch(Path("/repo")) == "master"


class TestRunnerPublicSurface:
    """Unit-scope invariants on the runner module's __all__."""

    def test_all_has_no_duplicates(self) -> None:
        """AC1: ``runner.__all__`` exposes each symbol exactly once."""
        assert len(runner.__all__) == len(set(runner.__all__))


class TestGhAvailable:
    """Test gh_available helper."""

    @patch("axm_git.core.runner.shutil.which", return_value=None)
    def test_gh_not_installed(self, _which: MagicMock) -> None:
        assert gh_available() is False

    @patch("axm_git.core.runner.subprocess.run")
    @patch("axm_git.core.runner.shutil.which", return_value="/usr/bin/gh")
    def test_gh_installed_auth_ok(self, _which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh"], returncode=0, stdout="", stderr=""
        )
        assert gh_available() is True

    @patch("axm_git.core.runner.subprocess.run")
    @patch("axm_git.core.runner.shutil.which", return_value="/usr/bin/gh")
    def test_gh_installed_auth_fail(
        self, _which: MagicMock, mock_run: MagicMock
    ) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh"], returncode=1, stdout="", stderr="not logged in"
        )
        assert gh_available() is False


class TestRunGh:
    """Test run_gh helper."""

    @patch("axm_git.core.runner.subprocess.run")
    def test_run_gh_delegates(self, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh"], returncode=0, stdout="ok", stderr=""
        )
        result = run_gh(["auth", "status"], Path("/tmp"))
        assert result.returncode == 0
        assert result.stdout == "ok"
        mock_run.assert_called_once()


class TestRunnerTimeouts:
    """AC1, AC2, AC3 — explicit subprocess timeouts."""

    @patch("axm_git.core.runner.subprocess.run")
    def test_run_git_passes_default_timeout(self, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["git"], returncode=0, stdout="", stderr=""
        )
        run_git(["status"], cwd=Path("/tmp"))
        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 30.0

    @patch("axm_git.core.runner.subprocess.run")
    def test_run_git_caller_timeout_overrides_default(
        self, mock_run: MagicMock
    ) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["git"], returncode=0, stdout="", stderr=""
        )
        run_git(["status"], cwd=Path("/tmp"), timeout=5.0)
        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 5.0

    @patch("axm_git.core.runner.subprocess.run")
    def test_run_gh_passes_default_timeout(self, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh"], returncode=0, stdout="", stderr=""
        )
        run_gh(["pr", "list"], cwd=Path("/tmp"))
        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 120.0

    @patch(
        "axm_git.core.runner.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["git"], timeout=30.0),
    )
    def test_find_git_root_returns_none_on_timeout(self, _mock_run: MagicMock) -> None:
        assert find_git_root(Path("/tmp")) is None

    @patch(
        "axm_git.core.runner.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["gh"], timeout=30.0),
    )
    @patch("axm_git.core.runner.shutil.which", return_value="/usr/bin/gh")
    def test_gh_available_returns_false_on_timeout(
        self, _which: MagicMock, _mock_run: MagicMock
    ) -> None:
        assert gh_available() is False


class TestStagedDelta:
    """Unit tests for staged_delta (pure)."""

    def test_returns_only_newly_staged_paths(self) -> None:
        """The delta excludes third-party paths staged before the call."""
        before = {"third_party.py"}
        after = {"third_party.py", "op_a.py", "op_b.py"}
        assert runner.staged_delta(before, after) == ["op_a.py", "op_b.py"]

    def test_empty_when_nothing_new_staged(self) -> None:
        shared = {"already.py"}
        assert runner.staged_delta(shared, shared) == []

    def test_output_is_sorted(self) -> None:
        assert runner.staged_delta(set(), {"z.py", "a.py", "m.py"}) == [
            "a.py",
            "m.py",
            "z.py",
        ]


class TestResetPaths:
    """Unit tests for reset_paths (scoped git reset)."""

    @patch("axm_git.core.runner.run_git")
    def test_scoped_reset_of_given_paths(self, mock_run_git: MagicMock) -> None:
        runner.reset_paths(["a.py", "b.py"], Path("/repo"))
        args, _ = mock_run_git.call_args
        assert args[0] == ["reset", "--quiet", "--", "a.py", "b.py"]

    @patch("axm_git.core.runner.run_git")
    def test_empty_paths_is_a_noop(self, mock_run_git: MagicMock) -> None:
        """A bare ``git reset`` (whole index) is never issued for empty paths."""
        runner.reset_paths([], Path("/repo"))
        mock_run_git.assert_not_called()
