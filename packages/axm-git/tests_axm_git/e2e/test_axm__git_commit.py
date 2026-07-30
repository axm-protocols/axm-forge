"""E2E: ``axm git_commit`` stages and commits a deletion (black-box CLI).

Drives the real CLI (``python -m axm.cli git_commit``) against a temporary git
repository built by subprocess, deletes a tracked file, and asserts the single
new commit carries the deletion. No mocking — the whole AXMTool → CLI → git
pipeline runs for real.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


def _init_repo(repo: Path) -> None:
    _git(["init", "-q", "-b", "main"], repo)
    _git(["config", "user.email", "test@example.com"], repo)
    _git(["config", "user.name", "Test"], repo)
    _git(["config", "commit.gpgsign", "false"], repo)
    (repo / "keep.py").write_text("keep\n")
    (repo / "drop.py").write_text("drop\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "chore: init"], repo)


def test_axm_git_commit_commits_a_deletion(tmp_path: Path) -> None:
    """AC2: ``axm git_commit`` on a spec with a deleted path commits the deletion."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)

    # Delete a tracked file on disk, then commit it via the CLI.
    (repo / "drop.py").unlink()
    before = int(_git(["rev-list", "--count", "HEAD"], repo).stdout.strip())

    spec = json.dumps([{"files": ["drop.py"], "message": "chore: remove drop.py"}])
    env = {"HOME": str(tmp_path / "home"), "PATH": os.environ["PATH"]}
    (tmp_path / "home").mkdir()

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "axm.cli",
            "git_commit",
            "--path",
            str(repo),
            "--commits",
            spec,
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    after = int(_git(["rev-list", "--count", "HEAD"], repo).stdout.strip())
    assert after == before + 1

    show = _git(["show", "--name-status", "--format=", "HEAD"], repo)
    assert "D\tdrop.py" in show.stdout

    tracked = _git(["ls-tree", "-r", "--name-only", "HEAD"], repo).stdout
    assert "drop.py" not in tracked.splitlines()
