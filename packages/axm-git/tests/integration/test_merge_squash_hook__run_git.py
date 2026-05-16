"""Split from ``test_merge_squash.py``."""

from pathlib import Path

from axm_git.core.runner import run_git
from axm_git.hooks.merge_squash import MergeSquashHook


def test_merge_squash(tmp_git_repo_with_branch: Path) -> None:
    hook = MergeSquashHook()
    result = hook.execute(
        {
            "working_dir": str(tmp_git_repo_with_branch),
            "session_id": "abc",
            "protocol_name": "sota-express",
        },
    )
    assert result.success
    assert result.metadata["merged"] == "axm/abc"
    assert result.metadata["into"] == "main"
    assert result.metadata["message"] == "[AXM] sota-express: abc"
    # Verify we are on main
    branch = run_git(["branch", "--show-current"], tmp_git_repo_with_branch)
    assert branch.stdout.strip() == "main"


def test_target_branch_missing(tmp_git_repo: Path) -> None:
    """Fail when target branch does not exist."""
    run_git(["checkout", "-b", "axm/session"], tmp_git_repo)
    hook = MergeSquashHook()
    result = hook.execute(
        {
            "working_dir": str(tmp_git_repo),
            "session_id": "session",
            "protocol_name": "p",
        },
        target_branch="nonexistent",
    )
    assert not result.success


def test_subdirectory_of_git_repo(tmp_workspace_repo: tuple[Path, Path]) -> None:
    """Merge succeeds when working_dir is a subdirectory of a git repo."""
    git_root, pkg_dir = tmp_workspace_repo
    run_git(["checkout", "-b", "axm/sub"], git_root)
    (pkg_dir / "src" / "change.py").write_text("# new\n")
    run_git(["add", "."], git_root)
    run_git(["commit", "-m", "session work"], git_root)

    hook = MergeSquashHook()
    result = hook.execute(
        {
            "working_dir": str(pkg_dir),
            "session_id": "sub",
            "protocol_name": "p",
        },
    )
    assert result.success
    assert result.metadata["merged"] == "axm/sub"
    assert result.metadata["into"] == "main"
    # Verify we landed on main at repo root
    branch = run_git(["branch", "--show-current"], git_root)
    assert branch.stdout.strip() == "main"
