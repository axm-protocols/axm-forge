"""Integration tests for resolve_default_branch against a real git repo."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_git.core.runner import resolve_default_branch, run_git

pytestmark = pytest.mark.integration


def test_resolve_default_branch_master_repo(tmp_path: Path) -> None:
    """AC4: a repo whose origin/HEAD points to master resolves to \"master\"."""
    origin = tmp_path / "origin"
    clone = tmp_path / "clone"
    run_git(["init", "-b", "master", str(origin)], tmp_path)
    run_git(["config", "user.email", "test@test.com"], origin)
    run_git(["config", "user.name", "Test"], origin)
    (origin / "f.txt").write_text("x\n")
    run_git(["add", "."], origin)
    run_git(["commit", "-m", "init"], origin)
    run_git(["clone", str(origin), str(clone)], tmp_path)

    assert resolve_default_branch(clone) == "master"
