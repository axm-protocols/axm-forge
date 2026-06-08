"""Functional tests for axm-git tools against real git repos."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_git.tools.push import GitPushTool


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a git command in ``cwd``, capturing text output."""
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
    )


def _init_repo(path: Path) -> None:
    """Initialize a git repo with an initial commit."""
    subprocess.run(["git", "init"], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    # Initial commit
    readme = path / "README.md"
    readme.write_text("# Test\n")
    subprocess.run(["git", "add", "."], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "chore: init", "--no-verify"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )


class TestPushFlow:
    """Functional tests for git_push."""

    def test_push_dirty_rejected(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)

        # Modify a file without committing.
        (tmp_path / "README.md").write_text("# Modified\n")

        result = GitPushTool().execute(path=str(tmp_path))
        assert not result.success
        assert "dirty" in (result.error or "").lower()
        assert "README.md" in result.data["dirty_files"]

    @pytest.mark.integration
    def test_force_with_lease_real_push(self, tmp_path: Path) -> None:
        """AC1: force=True uses --force-with-lease — a stale local is rejected.

        Proves lease semantics (not bare --force): when the remote has moved
        beyond the local remote-tracking ref, the force push is refused rather
        than overwriting the remote's new commit.
        """
        bare = tmp_path / "remote.git"
        bare.mkdir()
        _git(["init", "--bare"], bare)

        # Clone A: establishes the remote-tracking baseline.
        clone_a = tmp_path / "clone_a"
        _git(["clone", str(bare), str(clone_a)], tmp_path)
        _git(["config", "user.email", "a@test.com"], clone_a)
        _git(["config", "user.name", "A"], clone_a)
        _git(["config", "commit.gpgsign", "false"], clone_a)
        (clone_a / "f.txt").write_text("a1\n")
        _git(["add", "."], clone_a)
        _git(["commit", "-m", "a1", "--no-verify"], clone_a)
        _git(["push", "origin", "HEAD:main"], clone_a)
        _git(["branch", "--set-upstream-to=origin/main"], clone_a)

        # Clone B advances the remote beyond A's stale tracking ref.
        clone_b = tmp_path / "clone_b"
        _git(["clone", str(bare), str(clone_b)], tmp_path)
        _git(["config", "user.email", "b@test.com"], clone_b)
        _git(["config", "user.name", "B"], clone_b)
        _git(["config", "commit.gpgsign", "false"], clone_b)
        (clone_b / "f.txt").write_text("b1\n")
        _git(["add", "."], clone_b)
        _git(["commit", "-m", "b1", "--no-verify"], clone_b)
        _git(["push", "origin", "HEAD:main"], clone_b)

        # A rewrites history locally (stale vs remote) and force-pushes.
        (clone_a / "f.txt").write_text("a2\n")
        _git(["add", "."], clone_a)
        _git(["commit", "--amend", "-m", "a2", "--no-verify"], clone_a)

        result = GitPushTool().execute(path=str(clone_a), force=True)

        # Lease protects the remote: push is rejected, not overwritten.
        assert not result.success
        assert (
            "stale info" in (result.error or "").lower()
            or "force-with-lease" in (result.error or "").lower()
            or "rejected" in (result.error or "").lower()
        )
