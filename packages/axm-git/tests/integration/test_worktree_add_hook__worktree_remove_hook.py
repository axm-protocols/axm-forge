"""Functional test: worktree add → use → remove roundtrip."""

from __future__ import annotations

from pathlib import Path

from axm_git.hooks.worktree_add import WorktreeAddHook
from axm_git.hooks.worktree_remove import WorktreeRemoveHook


def test_dirty_worktree_force_remove(tmp_git_repo: Path) -> None:
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
