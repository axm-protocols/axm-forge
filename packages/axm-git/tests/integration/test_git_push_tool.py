"""Functional tests for axm-git tools against real git repos."""

from __future__ import annotations

import subprocess
from pathlib import Path

from axm_git.tools.push import GitPushTool


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
