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

    def test_create_branch_ticket_based(self, tmp_git_repo: Path) -> None:
        """Branch name from ticket_id + ticket_title + ticket_labels."""
        hook = CreateBranchHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "session_id": "ignored"},
            ticket_id="AXM-42",
            ticket_title="Add batch mode",
            ticket_labels=["feature"],
        )
        assert result.success
        assert result.metadata["branch"] == "feat/AXM-42-add-batch-mode"

    def test_create_branch_direct_param(self, tmp_git_repo: Path) -> None:
        """Direct branch param override."""
        hook = CreateBranchHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "session_id": "ignored"},
            branch="custom/name",
        )
        assert result.success
        assert result.metadata["branch"] == "custom/name"

    def test_create_branch_param_overrides_ticket(self, tmp_git_repo: Path) -> None:
        """branch param takes priority over ticket params."""
        hook = CreateBranchHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "session_id": "ignored"},
            branch="override/branch",
            ticket_id="AXM-42",
            ticket_title="Add batch mode",
        )
        assert result.success
        assert result.metadata["branch"] == "override/branch"

    def test_create_branch_session_fallback(self, tmp_git_repo: Path) -> None:
        """Falls back to {prefix}/{session_id} with no branch/ticket params."""
        hook = CreateBranchHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "session_id": "sess-001"},
        )
        assert result.success
        assert result.metadata["branch"] == "axm/sess-001"

    def test_missing_ticket_title_falls_back(self, tmp_git_repo: Path) -> None:
        """ticket_id without ticket_title falls back to session_id naming."""
        hook = CreateBranchHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "session_id": "sess-002"},
            ticket_id="AXM-99",
        )
        assert result.success
        assert result.metadata["branch"] == "axm/sess-002"

    def test_empty_labels(self, tmp_git_repo: Path) -> None:
        """Empty labels list defaults to 'feat' type via branch_name_from_ticket."""
        hook = CreateBranchHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "session_id": "ignored"},
            ticket_id="AXM-10",
            ticket_title="Fix something",
            ticket_labels=[],
        )
        assert result.success
        assert result.metadata["branch"] == "feat/AXM-10-fix-something"
