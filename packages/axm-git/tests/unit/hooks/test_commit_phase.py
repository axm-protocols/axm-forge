"""Tests for CommitPhaseHook."""

from __future__ import annotations

from pathlib import Path

from axm_git.hooks.commit_phase import CommitPhaseHook


class TestCommitPhaseHook:
    """Tests for CommitPhaseHook."""

    def test_commits_changes(self, tmp_git_repo: Path) -> None:
        (tmp_git_repo / "file.txt").write_text("hello")
        hook = CommitPhaseHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "phase_name": "plan"},
        )
        assert result.success
        assert result.metadata["message"] == "[axm] plan"
        assert result.metadata["commit"]  # short hash is non-empty

    def test_nothing_to_commit(self, tmp_git_repo: Path) -> None:
        hook = CommitPhaseHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "phase_name": "plan"},
        )
        assert result.success
        assert result.metadata["skipped"] is True

    def test_custom_message_format(self, tmp_git_repo: Path) -> None:
        (tmp_git_repo / "f.txt").write_text("x")
        hook = CommitPhaseHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "phase_name": "plan"},
            message_format="[AXM:{phase}]",
        )
        assert result.success
        assert result.metadata["message"] == "[AXM:plan]"

    def test_not_git_repo(self, tmp_path: Path) -> None:
        hook = CommitPhaseHook()
        result = hook.execute(
            {"working_dir": str(tmp_path), "phase_name": "p"},
        )
        assert result.success
        assert result.metadata["skipped"] is True

    def test_disabled(self, tmp_git_repo: Path) -> None:
        """Hook skips when enabled=False."""
        hook = CommitPhaseHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "phase_name": "plan"},
            enabled=False,
        )
        assert result.success
        assert result.metadata.get("skipped") is True
        assert result.metadata.get("reason") == "git disabled"
