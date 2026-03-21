"""Tests for WorktreeAddHook."""

from __future__ import annotations

from pathlib import Path

import pytest

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

    def test_worktree_path_is_under_tmp(self, tmp_git_repo: Path) -> None:
        hook = WorktreeAddHook()
        result = hook.execute(_make_context(tmp_git_repo, ticket_id="AXM-30"))

        wt_path = Path(result.metadata["worktree_path"])
        assert wt_path.parent == Path("/tmp/axm-worktrees")
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


class TestWorktreeAddHookParamsOverride:
    """Regression tests: params take precedence over context (AXM-665)."""

    def test_params_override_context(self, tmp_git_repo: Path) -> None:
        """repo_path in **params overrides context value."""
        hook = WorktreeAddHook()
        context = _make_context(Path("/nonexistent"), ticket_id="AXM-70")
        result = hook.execute(
            context,
            repo_path=str(tmp_git_repo),
        )

        assert result.success
        assert not result.metadata.get("skipped")
        assert Path(result.metadata["worktree_path"]).exists()

    def test_fallback_to_context(self, tmp_git_repo: Path) -> None:
        """When params omit repo_path, context value is used (backward compat)."""
        hook = WorktreeAddHook()
        result = hook.execute(_make_context(tmp_git_repo, ticket_id="AXM-71"))

        assert result.success
        assert not result.metadata.get("skipped")

    def test_creates_worktree_from_non_git_cwd(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CWD is /tmp (non-git), but repo_path param points to valid repo."""
        monkeypatch.chdir(Path("/tmp"))
        assert not Path(".git").exists(), "CWD should not be a git repo"

        hook = WorktreeAddHook()
        result = hook.execute(
            {},
            repo_path=str(tmp_git_repo),
            ticket_id="AXM-72",
            ticket_title="fix(git): non-git cwd",
            ticket_labels=["worktree"],
        )

        assert result.success
        assert not result.metadata.get("skipped")
        assert Path(result.metadata["worktree_path"]).exists()

    def test_all_fields_from_params(self, tmp_git_repo: Path) -> None:
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
