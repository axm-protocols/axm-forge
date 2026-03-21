"""Tests for WorktreeRemoveHook."""

from __future__ import annotations

from pathlib import Path

from axm_git.core.runner import run_git
from axm_git.hooks.worktree_add import WorktreeAddHook
from axm_git.hooks.worktree_remove import WorktreeRemoveHook


class TestWorktreeRemoveHook:
    """Tests for WorktreeRemoveHook."""

    def _add_worktree(self, repo: Path) -> dict[str, str]:
        """Helper: add a worktree and return its metadata."""
        hook = WorktreeAddHook()
        result = hook.execute(
            {
                "repo_path": str(repo),
                "ticket_id": "AXM-99",
                "ticket_title": "cleanup test",
                "ticket_labels": [],
            }
        )
        return dict(result.metadata)

    def test_removes_worktree(self, tmp_git_repo: Path) -> None:
        meta = self._add_worktree(tmp_git_repo)
        wt_path = meta["worktree_path"]

        hook = WorktreeRemoveHook()
        result = hook.execute(
            {
                "repo_path": str(tmp_git_repo),
                "worktree_path": wt_path,
            }
        )

        assert result.success
        assert not Path(wt_path).exists()

        wt_list = run_git(["worktree", "list"], tmp_git_repo)
        assert "AXM-99" not in wt_list.stdout

    def test_skip_missing_path(self, tmp_git_repo: Path) -> None:
        hook = WorktreeRemoveHook()
        result = hook.execute(
            {
                "repo_path": str(tmp_git_repo),
                "worktree_path": "/nonexistent/path",
            }
        )

        assert result.success
        assert result.metadata["skipped"] is True

    def test_disabled(self, tmp_git_repo: Path) -> None:
        hook = WorktreeRemoveHook()
        result = hook.execute(
            {"repo_path": str(tmp_git_repo), "worktree_path": "/tmp/x"},
            enabled=False,
        )

        assert result.success
        assert result.metadata["skipped"] is True

    def test_worktree_remove_dict_worktree_path(
        self,
        tmp_git_repo: Path,
    ) -> None:
        """Dict worktree_path in context is unwrapped without TypeError."""
        meta = self._add_worktree(tmp_git_repo)
        wt_path = meta["worktree_path"]

        hook = WorktreeRemoveHook()
        result = hook.execute(
            {
                "repo_path": str(tmp_git_repo),
                "worktree_path": {
                    "worktree_path": wt_path,
                    "branch": "feat/x",
                },
            }
        )

        assert result.success
        assert not Path(wt_path).exists()

    def test_skip_not_git_repo(self, tmp_path: Path) -> None:
        hook = WorktreeRemoveHook()
        result = hook.execute(
            {
                "repo_path": str(tmp_path),
                "worktree_path": str(tmp_path / "wt"),
            }
        )

        assert result.success
        assert result.metadata["skipped"] is True
