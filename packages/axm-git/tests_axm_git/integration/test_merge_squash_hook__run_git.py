"""Integration tests for MergeSquashHook over real temp repos."""

from __future__ import annotations

from pathlib import Path

import axm_config
import pytest

from axm_git.core.runner import run_git
from axm_git.hooks.merge_squash import MergeSquashHook

pytestmark = pytest.mark.integration


def test_squash_commit_uses_resolved_profile(
    tmp_git_repo_with_branch: Path,
    scrubbed_axm_home: Path,
) -> None:
    """AXM-1826 AC1: squash commit author equals the resolved profile.

    AXM-2329 contract: ``load_config(config_path=None)`` resolves the identity
    from the ``axm_config`` single store ``[git.default]`` namespace. Under the
    hermetic ``scrubbed_axm_home`` fixture the store is built in ``tmp_path``
    (``HOME`` redirected there, ``AXM_*``/git-config env scrubbed), so the
    resolved author is exactly the injected profile with zero machine-state
    dependency — no ambient ``~/.axm`` and no global git config leak in.
    """
    axm_config.set_(
        "git",
        "default",
        {"name": "Squash Bot", "email": "squash@axm-protocol.io"},
    )

    result = MergeSquashHook().execute(
        {
            "working_dir": str(tmp_git_repo_with_branch),
            "session_id": "abc",
            "protocol_name": "p",
        },
    )

    assert result.success is True
    log = run_git(["log", "-1", "--format=%an <%ae>"], tmp_git_repo_with_branch)
    assert log.stdout.strip() == "Squash Bot <squash@axm-protocol.io>"


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
