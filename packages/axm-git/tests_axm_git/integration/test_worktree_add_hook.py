"""Tests for WorktreeAddHook."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_git.core.runner import run_git
from axm_git.hooks import worktree_add
from axm_git.hooks.worktree_add import WorktreeAddHook
from tests_axm_git.integration._helpers import _make_context


def test_worktree_path_is_under_the_default_root(tmp_git_repo: Path) -> None:
    """With no root given, the worktree lands under the resolved default.

    Asserting against ``worktree_add.DEFAULT_WORKTREE_ROOT`` rather than the
    literal ``/tmp/axm-worktrees``: the conftest points that default at a
    per-test directory so tests cannot collide, and the contract under test is
    "<root>/<ticket_id>", not which root the machine happens to use.
    """
    hook = WorktreeAddHook()
    result = hook.execute(_make_context(tmp_git_repo, ticket_id="AXM-30"))

    wt_path = Path(result.metadata["worktree_path"])
    assert wt_path.parent == worktree_add.DEFAULT_WORKTREE_ROOT
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


class TestWorktreeRootIsConfigurable:
    """The worktree root is a configuration decision, not a code constant.

    Writing to a fixed ``/tmp/axm-worktrees/<ticket>`` makes two concurrent
    executions collide: the second finds the first's directory and fails with
    "a branch named … already exists". That is not a test artefact — the warden
    runs with ``--max-concurrent`` above 1, so two tickets touching the same repo
    hit it in production. Surfaced by running the suite under xdist, where four
    worktree tests broke at once.

    Resolution order follows the house convention: an explicit ``worktree_root``
    in the context wins, then the ``git.worktree_root`` config key, then the
    historical default — so existing callers see no change.
    """

    def test_context_root_overrides_the_default(self, tmp_git_repo: Path) -> None:
        """AC1: an explicit root in the context is where the worktree lands."""
        root = tmp_git_repo.parent / "wt-root"
        ctx = _make_context(tmp_git_repo, ticket_id="AXM-70")
        ctx["worktree_root"] = str(root)

        result = WorktreeAddHook().execute(ctx)

        assert result.success, result.error
        assert Path(result.metadata["worktree_path"]).parent == root

    def test_two_repos_do_not_collide_under_a_shared_ticket_id(
        self, tmp_git_repo: Path, tmp_path: Path
    ) -> None:
        """AC2: same ticket id, two roots -> two independent worktrees.

        This is the concurrency case in miniature: without a configurable root
        the second call would find the first's directory and skip (or fail).
        """
        second = tmp_path / "repo-b"
        second.mkdir()
        run_git(["init", "-b", "main"], second)
        run_git(["config", "user.email", "t@t.com"], second)
        run_git(["config", "user.name", "T"], second)
        (second / ".gitkeep").touch()
        run_git(["add", "."], second)
        run_git(["commit", "-m", "init"], second)

        first_ctx = _make_context(tmp_git_repo, ticket_id="AXM-71")
        first_ctx["worktree_root"] = str(tmp_path / "root-a")
        second_ctx = _make_context(second, ticket_id="AXM-71")
        second_ctx["worktree_root"] = str(tmp_path / "root-b")

        first = WorktreeAddHook().execute(first_ctx)
        other = WorktreeAddHook().execute(second_ctx)

        assert first.success, first.error
        assert other.success, other.error
        assert other.metadata.get("skipped") is not True
        assert first.metadata["worktree_path"] != other.metadata["worktree_path"]
