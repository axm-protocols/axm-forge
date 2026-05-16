"""Split from ``test_worktree_add.py``."""

from pathlib import Path

from axm_git.core.branch_naming import branch_name_from_ticket
from axm_git.hooks.worktree_add import WorktreeAddHook
from tests.integration._helpers import _make_context


def test_branch_naming(tmp_git_repo: Path) -> None:
    hook = WorktreeAddHook()
    tid, title, labels = "AXM-20", "feat(git): worktree hooks", ["worktree"]
    result = hook.execute(
        _make_context(tmp_git_repo, ticket_id=tid, title=title, labels=labels),
    )

    expected = branch_name_from_ticket(tid, title, labels)
    assert result.metadata["branch"] == expected


def test_all_fields_from_params(tmp_git_repo: Path) -> None:
    """All four fields passed as params, empty context."""
    hook = WorktreeAddHook()
    result = hook.execute(
        {},
        repo_path=str(tmp_git_repo),
        ticket_id="AXM-73",
        ticket_title="feat(git): all params",
        ticket_labels=["worktree"],
    )

    assert result.success
    assert not result.metadata.get("skipped")
    expected_branch = branch_name_from_ticket(
        "AXM-73", "feat(git): all params", ["worktree"]
    )
    assert result.metadata["branch"] == expected_branch
