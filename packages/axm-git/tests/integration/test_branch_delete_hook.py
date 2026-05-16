"""Split from ``test_branch_delete.py``."""

from pathlib import Path

from axm_git.hooks.branch_delete import BranchDeleteHook


def test_branch_delete_missing_branch(tmp_git_repo: Path) -> None:
    """Fails with descriptive error when no branch specified."""
    hook = BranchDeleteHook()
    result = hook.execute(
        {"working_dir": str(tmp_git_repo), "session_id": "s"},
    )
    assert not result.success
    assert result.error is not None
    assert "no branch specified" in result.error


def test_branch_delete_not_found(tmp_git_repo: Path) -> None:
    """Fails when branch does not exist."""
    hook = BranchDeleteHook()
    result = hook.execute(
        {"working_dir": str(tmp_git_repo), "session_id": "s"},
        branch="nonexistent/branch",
    )
    assert not result.success
    assert result.error is not None
    assert "git branch -D failed" in result.error


def test_branch_delete_disabled(tmp_git_repo: Path) -> None:
    """Hook skips when enabled=False."""
    hook = BranchDeleteHook()
    result = hook.execute(
        {"working_dir": str(tmp_git_repo), "session_id": "s"},
        enabled=False,
    )
    assert result.success
    assert result.metadata.get("skipped") is True
    assert result.metadata.get("reason") == "git disabled"


def test_branch_delete_not_git_repo(tmp_path: Path) -> None:
    """Hook skips when working dir is not a git repo."""
    hook = BranchDeleteHook()
    result = hook.execute(
        {"working_dir": str(tmp_path), "session_id": "s"},
    )
    assert result.success
    assert result.metadata["skipped"] is True
