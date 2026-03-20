"""Functional test: worktree add → use → remove roundtrip."""

from __future__ import annotations

from pathlib import Path

from axm_git.core.runner import run_git
from axm_git.hooks.worktree_add import WorktreeAddHook
from axm_git.hooks.worktree_remove import WorktreeRemoveHook


class TestWorktreeRoundtrip:
    """End-to-end worktree lifecycle."""

    def test_add_use_remove(self, tmp_git_repo: Path) -> None:
        ctx = {
            "repo_path": str(tmp_git_repo),
            "ticket_id": "AXM-77",
            "ticket_title": "roundtrip test",
            "ticket_labels": ["feat"],
        }

        # Add worktree
        add_result = WorktreeAddHook().execute(ctx)
        assert add_result.success
        wt_path = Path(add_result.metadata["worktree_path"])
        branch = add_result.metadata["branch"]

        # Work inside worktree
        (wt_path / "new_file.py").write_text("# new\n")
        run_git(["add", "."], wt_path)
        run_git(["commit", "-m", "work in worktree"], wt_path)

        # Verify branch exists
        branches = run_git(["branch", "--list", branch], tmp_git_repo)
        assert branch in branches.stdout

        # Remove worktree
        remove_result = WorktreeRemoveHook().execute(
            {
                "repo_path": str(tmp_git_repo),
                "worktree_path": str(wt_path),
            }
        )
        assert remove_result.success
        assert not wt_path.exists()

    def test_dirty_worktree_force_remove(self, tmp_git_repo: Path) -> None:
        ctx = {
            "repo_path": str(tmp_git_repo),
            "ticket_id": "AXM-88",
            "ticket_title": "dirty remove test",
            "ticket_labels": [],
        }

        add_result = WorktreeAddHook().execute(ctx)
        wt_path = Path(add_result.metadata["worktree_path"])

        # Leave uncommitted changes (dirty)
        (wt_path / "dirty.txt").write_text("uncommitted")

        # Force remove should still work
        remove_result = WorktreeRemoveHook().execute(
            {
                "repo_path": str(tmp_git_repo),
                "worktree_path": str(wt_path),
            }
        )
        assert remove_result.success
        assert not wt_path.exists()
