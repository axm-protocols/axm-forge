"""Split from ``test_worktree_roundtrip.py``."""

from pathlib import Path

from axm_git.core.runner import run_git
from axm_git.hooks.worktree_add import WorktreeAddHook
from axm_git.hooks.worktree_remove import WorktreeRemoveHook
from tests.integration._helpers import _make_context


def test_add_use_remove(tmp_git_repo: Path) -> None:
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


def test_creates_worktree(tmp_git_repo: Path) -> None:
    hook = WorktreeAddHook()
    result = hook.execute(_make_context(tmp_git_repo, ticket_id="AXM-10"))

    assert result.success
    wt_path = Path(result.metadata["worktree_path"])
    assert wt_path.exists()
    assert result.metadata["branch"]

    wt_list = run_git(["worktree", "list"], tmp_git_repo)
    assert "AXM-10" in wt_list.stdout
