"""Tests for WorktreeAddHook."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_git.hooks.worktree_add import WorktreeAddHook
from tests.integration._helpers import _make_context


def test_worktree_path_is_under_tmp(tmp_git_repo: Path) -> None:
    hook = WorktreeAddHook()
    result = hook.execute(_make_context(tmp_git_repo, ticket_id="AXM-30"))

    wt_path = Path(result.metadata["worktree_path"])
    assert wt_path.parent == Path("/tmp/axm-worktrees")
    assert wt_path.name == "AXM-30"


def test_skip_not_git_repo(tmp_path: Path) -> None:
    hook = WorktreeAddHook()
    result = hook.execute(_make_context(tmp_path, ticket_id="AXM-40"))

    assert result.success
    assert result.metadata["skipped"] is True


def test_skip_existing_worktree(tmp_git_repo: Path) -> None:
    hook = WorktreeAddHook()
    ctx = _make_context(tmp_git_repo, ticket_id="AXM-50")

    hook.execute(ctx)
    result = hook.execute(ctx)

    assert result.success
    assert result.metadata.get("skipped") is True


def test_disabled(tmp_git_repo: Path) -> None:
    hook = WorktreeAddHook()
    result = hook.execute(
        _make_context(tmp_git_repo, ticket_id="AXM-60"),
        enabled=False,
    )

    assert result.success
    assert result.metadata["skipped"] is True
    assert result.metadata["reason"] == "git disabled"


def test_params_override_context(tmp_git_repo: Path) -> None:
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


def test_fallback_to_context(tmp_git_repo: Path) -> None:
    """When params omit repo_path, context value is used (backward compat)."""
    hook = WorktreeAddHook()
    result = hook.execute(_make_context(tmp_git_repo, ticket_id="AXM-71"))

    assert result.success
    assert not result.metadata.get("skipped")


def test_creates_worktree_from_non_git_cwd(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
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
