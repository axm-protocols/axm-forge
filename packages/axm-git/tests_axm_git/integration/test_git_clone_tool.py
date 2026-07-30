"""Integration tests for GitCloneTool against a real local git repository."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_git.tools.clone import GitCloneTool


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
    readme = path / "README.md"
    readme.write_text("# Test\n")
    subprocess.run(["git", "add", "."], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "chore: init", "--no-verify"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )


@pytest.mark.integration
class TestCloneFlow:
    """Functional tests for git_clone using local repositories."""

    def test_clone_local_repo_success(self, tmp_path: Path) -> None:
        """Clone a local source repo and verify the clone exists with content."""
        source = tmp_path / "source"
        source.mkdir()
        _init_repo(source)

        clone_parent = tmp_path / "workspace"
        clone_parent.mkdir()

        result = GitCloneTool().execute(
            url=str(source),
            dest="my-clone",
            path=str(clone_parent),
        )

        assert result.success
        assert result.data["cloned"] is True
        assert result.data["url"] == str(source)
        assert result.data["dest"] == "my-clone"
        clone_dir = Path(result.data["path"])
        assert clone_dir.exists()
        assert (clone_dir / "README.md").exists()

    def test_clone_invalid_url_fails(self, tmp_path: Path) -> None:
        """Clone from a non-existent path returns a failure ToolResult."""
        result = GitCloneTool().execute(
            url="/nonexistent/repo",
            dest="clone",
            path=str(tmp_path),
        )

        assert not result.success
        assert result.error
