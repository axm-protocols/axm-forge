"""Integration tests for MergeSquashHook over real temp repos."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_git.core.runner import run_git
from axm_git.hooks.merge_squash import MergeSquashHook

pytestmark = pytest.mark.integration

_PROFILE_TOML = """\
[default]
name = "Squash Bot"
email = "squash@axm-protocol.io"
"""


def test_squash_commit_uses_resolved_profile(
    tmp_git_repo_with_branch: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AXM-1826 AC1: squash commit author equals the resolved profile.

    AXM-2329 contract: ``load_config(config_path=None)`` now resolves from the
    axm_config store first, falling back to the legacy ``~/axm/git-profiles.toml``
    only when the ``[git]`` section is absent. HOME is redirected to an empty
    tmp dir (no store ``[git]`` section) and the legacy file is planted at the
    resolved ``~/axm/git-profiles.toml`` so the legacy-fallback path resolves
    the profile.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("USERPROFILE", raising=False)
    legacy_dir = home / "axm"
    legacy_dir.mkdir()
    (legacy_dir / "git-profiles.toml").write_text(_PROFILE_TOML)

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
