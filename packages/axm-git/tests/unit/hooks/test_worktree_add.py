"""Tests for WorktreeAddHook."""

from __future__ import annotations

from pathlib import Path

from axm_git.core.branch_naming import branch_name_from_ticket
from axm_git.core.runner import run_git
from axm_git.hooks.worktree_add import WorktreeAddHook


def _make_context(
    repo: Path,
    ticket_id: str = "AXM-42",
    title: str = "feat(git): worktree hooks",
    labels: list[str] | None = None,
) -> dict[str, str | list[str]]:
    return {
        "repo_path": str(repo),
        "ticket_id": ticket_id,
        "ticket_title": title,
        "ticket_labels": labels if labels is not None else ["worktree"],
    }


class TestWorktreeAddHook:
    """Tests for WorktreeAddHook."""

    def test_creates_worktree(self, tmp_git_repo: Path) -> None:
        hook = WorktreeAddHook()
        result = hook.execute(_make_context(tmp_git_repo, ticket_id="AXM-10"))

        assert result.success
        wt_path = Path(result.metadata["worktree_path"])
        assert wt_path.exists()
        assert result.metadata["branch"]

        wt_list = run_git(["worktree", "list"], tmp_git_repo)
        assert "AXM-10" in wt_list.stdout

    def test_branch_naming(self, tmp_git_repo: Path) -> None:
        hook = WorktreeAddHook()
        tid, title, labels = "AXM-20", "feat(git): worktree hooks", ["worktree"]
        result = hook.execute(
            _make_context(tmp_git_repo, ticket_id=tid, title=title, labels=labels),
        )

        expected = branch_name_from_ticket(tid, title, labels)
        assert result.metadata["branch"] == expected

    def test_worktree_path_is_sibling(self, tmp_git_repo: Path) -> None:
        hook = WorktreeAddHook()
        result = hook.execute(_make_context(tmp_git_repo, ticket_id="AXM-30"))

        wt_path = Path(result.metadata["worktree_path"])
        assert wt_path.parent == tmp_git_repo.parent
        assert wt_path.name == "AXM-30"

    def test_skip_not_git_repo(self, tmp_path: Path) -> None:
        hook = WorktreeAddHook()
        result = hook.execute(_make_context(tmp_path, ticket_id="AXM-40"))

        assert result.success
        assert result.metadata["skipped"] is True

    def test_skip_existing_worktree(self, tmp_git_repo: Path) -> None:
        hook = WorktreeAddHook()
        ctx = _make_context(tmp_git_repo, ticket_id="AXM-50")

        hook.execute(ctx)
        result = hook.execute(ctx)

        assert result.success
        assert result.metadata.get("skipped") is True

    def test_disabled(self, tmp_git_repo: Path) -> None:
        hook = WorktreeAddHook()
        result = hook.execute(
            _make_context(tmp_git_repo, ticket_id="AXM-60"),
            enabled=False,
        )

        assert result.success
        assert result.metadata["skipped"] is True
        assert result.metadata["reason"] == "git disabled"
