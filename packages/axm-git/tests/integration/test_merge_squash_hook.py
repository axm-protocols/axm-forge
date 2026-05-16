"""Tests for MergeSquashHook."""

from __future__ import annotations

from pathlib import Path

from axm_git.hooks.merge_squash import MergeSquashHook


def test_not_git_repo(tmp_path: Path) -> None:
    result = MergeSquashHook().execute(
        {
            "working_dir": str(tmp_path),
            "session_id": "x",
            "protocol_name": "p",
        },
    )
    assert result.success
    assert result.metadata["skipped"] is True


def test_disabled(tmp_git_repo: Path) -> None:
    """Hook skips when enabled=False."""
    hook = MergeSquashHook()
    result = hook.execute(
        {
            "working_dir": str(tmp_git_repo),
            "session_id": "abc",
            "protocol_name": "p",
        },
        enabled=False,
    )
    assert result.success
    assert result.metadata.get("skipped") is True
    assert result.metadata.get("reason") == "git disabled"


def test_merge_squash_branch_from_params(tmp_git_repo_with_named_branch: Path) -> None:
    """branch param overrides session_id-based naming."""
    hook = MergeSquashHook()
    result = hook.execute(
        {
            "working_dir": str(tmp_git_repo_with_named_branch),
            "session_id": "ignored",
            "protocol_name": "p",
        },
        branch="feat/x",
    )
    assert result.success
    assert result.metadata["merged"] == "feat/x"


def test_merge_squash_branch_from_context(tmp_git_repo_with_named_branch: Path) -> None:
    """branch from context when not in params."""
    hook = MergeSquashHook()
    result = hook.execute(
        {
            "working_dir": str(tmp_git_repo_with_named_branch),
            "session_id": "ignored",
            "protocol_name": "p",
            "branch": "feat/x",
        },
    )
    assert result.success
    assert result.metadata["merged"] == "feat/x"


def test_merge_squash_custom_message(tmp_git_repo_with_branch: Path) -> None:
    """Custom commit message via message param."""
    hook = MergeSquashHook()
    result = hook.execute(
        {
            "working_dir": str(tmp_git_repo_with_branch),
            "session_id": "abc",
            "protocol_name": "sota-express",
        },
        message="feat(git): support ticket-based branch naming [AXM-676]",
    )
    assert result.success
    assert result.metadata["message"] == (
        "feat(git): support ticket-based branch naming [AXM-676]"
    )


def test_merge_squash_session_fallback(tmp_git_repo_with_branch: Path) -> None:
    """Falls back to {prefix}/{session_id} with no branch param or context."""
    hook = MergeSquashHook()
    result = hook.execute(
        {
            "working_dir": str(tmp_git_repo_with_branch),
            "session_id": "abc",
            "protocol_name": "p",
        },
    )
    assert result.success
    assert result.metadata["merged"] == "axm/abc"
    assert result.metadata["message"] == "[AXM] p: abc"
