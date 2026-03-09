"""Tests for CreateBranchHook."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_git.core.runner import run_git
from axm_git.hooks.create_branch import CreateBranchHook


class TestCreateBranchHook:
    """Tests for CreateBranchHook."""

    def test_creates_branch(self, tmp_git_repo: Path) -> None:
        hook = CreateBranchHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "session_id": "abc123"},
        )
        assert result.success
        assert result.metadata["branch"] == "axm/abc123"
        # Verify git branch exists
        branches = run_git(["branch"], tmp_git_repo)
        assert "axm/abc123" in branches.stdout

    def test_custom_prefix(self, tmp_git_repo: Path) -> None:
        hook = CreateBranchHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "session_id": "x"},
            prefix="feat",
        )
        assert result.success
        assert result.metadata["branch"] == "feat/x"

    def test_not_git_repo(self, tmp_path: Path) -> None:
        hook = CreateBranchHook()
        result = hook.execute(
            {"working_dir": str(tmp_path), "session_id": "x"},
        )
        assert result.success
        assert result.metadata["skipped"] is True

    def test_branch_exists_fails(self, tmp_git_repo: Path) -> None:
        hook = CreateBranchHook()
        hook.execute(
            {"working_dir": str(tmp_git_repo), "session_id": "x"},
        )
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "session_id": "x"},
        )
        assert not result.success

    def test_default_working_dir(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """working_dir defaults to '.' when missing from context."""
        monkeypatch.chdir(tmp_git_repo)
        hook = CreateBranchHook()
        result = hook.execute({"session_id": "z"})
        assert result.success
        assert result.metadata["branch"] == "axm/z"

    def test_disabled(self, tmp_git_repo: Path) -> None:
        """Hook skips when enabled=False."""
        hook = CreateBranchHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "session_id": "abc123"},
            enabled=False,
        )
        assert result.success
        assert result.metadata.get("skipped") is True
        assert result.metadata.get("reason") == "git disabled"
