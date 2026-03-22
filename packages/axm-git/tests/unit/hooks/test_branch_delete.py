"""Tests for BranchDeleteHook."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_git.core.runner import run_git
from axm_git.hooks.branch_delete import BranchDeleteHook


class TestBranchDeleteHook:
    """Tests for BranchDeleteHook."""

    def test_branch_delete_success(self, tmp_git_repo: Path) -> None:
        """Deletes an existing branch successfully."""
        # Create a branch to delete
        run_git(["checkout", "-b", "feat/x"], tmp_git_repo)
        run_git(["checkout", "main"], tmp_git_repo)

        hook = BranchDeleteHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "session_id": "s"},
            branch="feat/x",
        )
        assert result.success
        assert result.metadata["branch"] == "feat/x"
        assert result.metadata["deleted"] is True

        # Verify branch is gone
        branches = run_git(["branch"], tmp_git_repo)
        assert "feat/x" not in branches.stdout

    def test_branch_delete_from_params(self, tmp_git_repo: Path) -> None:
        """Branch name resolved from params."""
        run_git(["checkout", "-b", "feat/x"], tmp_git_repo)
        run_git(["checkout", "main"], tmp_git_repo)

        hook = BranchDeleteHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "session_id": "s"},
            branch="feat/x",
        )
        assert result.success
        assert result.metadata["branch"] == "feat/x"

    def test_branch_delete_from_context(self, tmp_git_repo: Path) -> None:
        """Branch name resolved from context when not in params."""
        run_git(["checkout", "-b", "feat/x"], tmp_git_repo)
        run_git(["checkout", "main"], tmp_git_repo)

        hook = BranchDeleteHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_git_repo),
                "session_id": "s",
                "branch": "feat/x",
            },
        )
        assert result.success
        assert result.metadata["branch"] == "feat/x"

    def test_branch_delete_params_override(self, tmp_git_repo: Path) -> None:
        """Params branch takes priority over context branch."""
        run_git(["checkout", "-b", "feat/x"], tmp_git_repo)
        run_git(["checkout", "main"], tmp_git_repo)

        hook = BranchDeleteHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_git_repo),
                "session_id": "s",
                "branch": "wrong/branch",
            },
            branch="feat/x",
        )
        assert result.success
        assert result.metadata["branch"] == "feat/x"

    def test_branch_delete_missing_branch(self, tmp_git_repo: Path) -> None:
        """Fails with descriptive error when no branch specified."""
        hook = BranchDeleteHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "session_id": "s"},
        )
        assert not result.success
        assert result.error is not None
        assert "no branch specified" in result.error

    def test_branch_delete_not_found(self, tmp_git_repo: Path) -> None:
        """Fails when branch does not exist."""
        hook = BranchDeleteHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "session_id": "s"},
            branch="nonexistent/branch",
        )
        assert not result.success
        assert result.error is not None
        assert "git branch -D failed" in result.error

    def test_branch_delete_disabled(self, tmp_git_repo: Path) -> None:
        """Hook skips when enabled=False."""
        hook = BranchDeleteHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "session_id": "s"},
            enabled=False,
        )
        assert result.success
        assert result.metadata.get("skipped") is True
        assert result.metadata.get("reason") == "git disabled"

    def test_branch_delete_not_git_repo(self, tmp_path: Path) -> None:
        """Hook skips when working dir is not a git repo."""
        hook = BranchDeleteHook()
        result = hook.execute(
            {"working_dir": str(tmp_path), "session_id": "s"},
        )
        assert result.success
        assert result.metadata["skipped"] is True

    def test_branch_delete_current_branch(self, tmp_git_repo: Path) -> None:
        """Fails when trying to delete the checked-out branch."""
        run_git(["checkout", "-b", "feat/current"], tmp_git_repo)

        hook = BranchDeleteHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "session_id": "s"},
            branch="feat/current",
        )
        assert not result.success
        assert result.error is not None
        assert "git branch -D failed" in result.error

    def test_subdirectory_of_git_repo(
        self, tmp_workspace_repo: tuple[Path, Path]
    ) -> None:
        """Delete succeeds when working_dir is a subdirectory of a git repo."""
        git_root, pkg_dir = tmp_workspace_repo
        run_git(["checkout", "-b", "feat/sub"], git_root)
        run_git(["checkout", "main"], git_root)

        hook = BranchDeleteHook()
        result = hook.execute(
            {"working_dir": str(pkg_dir), "session_id": "s"},
            branch="feat/sub",
        )
        assert result.success
        assert result.metadata["branch"] == "feat/sub"
        assert result.metadata["deleted"] is True
        # Verify branch is gone from repo root
        branches = run_git(["branch"], git_root)
        assert "feat/sub" not in branches.stdout

    def test_branch_delete_default_working_dir(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """working_dir defaults to '.' when missing from context."""
        run_git(["checkout", "-b", "feat/z"], tmp_git_repo)
        run_git(["checkout", "main"], tmp_git_repo)
        monkeypatch.chdir(tmp_git_repo)

        hook = BranchDeleteHook()
        result = hook.execute({"session_id": "s"}, branch="feat/z")
        assert result.success
        assert result.metadata["branch"] == "feat/z"
