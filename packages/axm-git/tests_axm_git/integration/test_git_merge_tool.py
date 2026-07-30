"""Integration tests for GitMergeTool against a real git repository."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_git.core.runner import run_git
from axm_git.tools.merge import GitMergeTool

pytestmark = pytest.mark.integration


def _init_repo(root: Path) -> None:
    run_git(["init", "-b", "main"], root)
    run_git(["config", "user.email", "test@test.com"], root)
    run_git(["config", "user.name", "Test"], root)
    (root / "shared.txt").write_text("line one\n")
    run_git(["add", "."], root)
    run_git(["commit", "-m", "init"], root)


def test_merge_conflict_restores_clean_tree(tmp_path: Path) -> None:
    """AC2: a squash-merge conflict is rolled back via reset --hard.

    Two branches edit the same line, forcing a squash conflict. After the
    failing call the working tree must be clean (no conflict markers).
    """
    _init_repo(tmp_path)
    # main edits the shared line
    (tmp_path / "shared.txt").write_text("main change\n")
    run_git(["add", "."], tmp_path)
    run_git(["commit", "-m", "main change"], tmp_path)
    # feat/x edits the same line from the original commit
    run_git(["checkout", "-b", "feat/x", "HEAD~1"], tmp_path)
    (tmp_path / "shared.txt").write_text("feat change\n")
    run_git(["add", "."], tmp_path)
    run_git(["commit", "-m", "feat change"], tmp_path)
    # leave the tree clean on feat/x before invoking the tool
    run_git(["checkout", "main"], tmp_path)

    result = GitMergeTool().execute(
        branch="feat/x", target_branch="main", path=str(tmp_path)
    )

    assert not result.success
    assert "merge --squash failed" in (result.error or "")
    status = run_git(["status", "--porcelain"], tmp_path)
    assert status.stdout.strip() == ""


def test_merge_squash_happy_path(tmp_path: Path) -> None:
    """AC3: a non-conflicting squash-merge succeeds and commits."""
    _init_repo(tmp_path)
    run_git(["checkout", "-b", "feat/x"], tmp_path)
    (tmp_path / "feature.txt").write_text("feature work\n")
    run_git(["add", "."], tmp_path)
    run_git(["commit", "-m", "feature commit"], tmp_path)
    run_git(["checkout", "main"], tmp_path)

    result = GitMergeTool().execute(
        branch="feat/x", target_branch="main", path=str(tmp_path)
    )

    assert result.success
    assert result.data["merged"] == "feat/x"
    assert result.data["into"] == "main"
    # the squashed change landed on main
    log = run_git(["log", "--oneline"], tmp_path)
    assert "Merge feat/x (squash)" in log.stdout
    assert (tmp_path / "feature.txt").exists()
