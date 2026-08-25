"""Split from ``test_create_branch.py``."""

from pathlib import Path

import pytest

from axm_git.core.runner import run_git
from axm_git.hooks.create_branch import CreateBranchHook


@pytest.mark.parametrize(
    ("subpath", "session_id"),
    [
        pytest.param("", "abc123", id="at_repo_root"),
        pytest.param("packages/pkg", "sub123", id="subdirectory_of_git_repo"),
    ],
)
def test_creates_branch(tmp_git_repo: Path, subpath: str, session_id: str) -> None:
    """Branch is created and visible from repo root for any starting cwd."""
    working_dir = tmp_git_repo / subpath if subpath else tmp_git_repo
    if subpath:
        working_dir.mkdir(parents=True)
    hook = CreateBranchHook()
    result = hook.execute(
        {"working_dir": str(working_dir), "session_id": session_id},
    )
    assert result.success
    expected_branch = f"axm/{session_id}"
    assert result.metadata["branch"] == expected_branch
    branches = run_git(["branch"], tmp_git_repo)
    assert expected_branch in branches.stdout
