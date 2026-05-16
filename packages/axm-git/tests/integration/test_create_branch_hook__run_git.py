"""Split from ``test_create_branch.py``."""

from pathlib import Path

from axm_git.core.runner import run_git
from axm_git.hooks.create_branch import CreateBranchHook


def test_creates_branch(tmp_git_repo: Path) -> None:
    hook = CreateBranchHook()
    result = hook.execute(
        {"working_dir": str(tmp_git_repo), "session_id": "abc123"},
    )
    assert result.success
    assert result.metadata["branch"] == "axm/abc123"
    # Verify git branch exists
    branches = run_git(["branch"], tmp_git_repo)
    assert "axm/abc123" in branches.stdout


def test_subdirectory_of_git_repo(tmp_git_repo: Path) -> None:
    """Branch created when working_dir is a subdirectory of a git repo."""
    subdir = tmp_git_repo / "packages" / "pkg"
    subdir.mkdir(parents=True)
    hook = CreateBranchHook()
    result = hook.execute(
        {"working_dir": str(subdir), "session_id": "sub123"},
    )
    assert result.success
    assert result.metadata["branch"] == "axm/sub123"
    # Branch visible from repo root
    branches = run_git(["branch"], tmp_git_repo)
    assert "axm/sub123" in branches.stdout
