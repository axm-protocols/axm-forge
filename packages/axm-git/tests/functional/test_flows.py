"""Functional tests for axm-git tools against real git repos."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_git.tools.branch import GitBranchTool
from axm_git.tools.commit import GitCommitTool
from axm_git.tools.commit_preflight import GitPreflightTool
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


class TestPreflightFlow:
    """Functional tests for git_preflight."""

    def test_preflight_shows_changes(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        # Modify a file
        (tmp_path / "README.md").write_text("# Modified\n")
        # Add a new file
        (tmp_path / "new.py").write_text("print('hello')\n")

        result = GitPreflightTool().execute(path=str(tmp_path))
        assert result.success
        assert not result.data["clean"]
        paths = [f["path"] for f in result.data["files"]]
        assert "README.md" in paths


class TestCommitFlow:
    """Functional tests for git_commit."""

    def test_commit_batch_end_to_end(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)

        # Create two changes
        (tmp_path / "a.py").write_text("# file a\n")
        (tmp_path / "b.py").write_text("# file b\n")

        result = GitCommitTool().execute(
            path=str(tmp_path),
            commits=[
                {"files": ["a.py"], "message": "feat: add a"},
                {"files": ["b.py"], "message": "fix: add b"},
            ],
        )
        assert result.success
        assert result.data["total"] == 2
        assert result.data["succeeded"] == 2

        # Verify git log
        log = subprocess.run(
            ["git", "log", "--oneline", "-3"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            check=True,
        )
        assert "feat: add a" in log.stdout
        assert "fix: add b" in log.stdout

    @pytest.mark.parametrize(
        "commits",
        [
            [{"files": ["nonexistent.py"], "message": "fix: ghost"}],
        ],
    )
    def test_commit_nonexistent_file(
        self, tmp_path: Path, commits: list[dict[str, object]]
    ) -> None:
        _init_repo(tmp_path)
        result = GitCommitTool().execute(
            path=str(tmp_path),
            commits=commits,
        )
        # git add on nonexistent file should fail
        assert not result.success

    def test_commit_deleted_file(self, tmp_path: Path) -> None:
        """Committing a deleted file works with git add -A."""
        _init_repo(tmp_path)

        # Create and commit a file
        target = tmp_path / "to_delete.py"
        target.write_text("# will be deleted\n")
        subprocess.run(
            ["git", "add", "."],
            cwd=str(tmp_path),
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "chore: add file", "--no-verify"],
            cwd=str(tmp_path),
            capture_output=True,
            check=True,
        )

        # Delete the file from disk
        target.unlink()

        # Commit the deletion via git_commit
        result = GitCommitTool().execute(
            path=str(tmp_path),
            commits=[{"files": ["to_delete.py"], "message": "fix: remove dead file"}],
        )
        assert result.success
        assert result.data["total"] == 1

        # Verify the file is no longer tracked
        ls = subprocess.run(
            ["git", "ls-files", "to_delete.py"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            check=True,
        )
        assert ls.stdout.strip() == ""


class TestBranchFlow:
    """Functional tests for git_branch."""

    def test_create_and_checkout(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)

        result = GitBranchTool().execute(name="feat/new", path=str(tmp_path))
        assert result.success
        assert result.data["branch"] == "feat/new"

        # Verify the branch exists in git branch output.
        branches = subprocess.run(
            ["git", "branch"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            check=True,
        )
        assert "feat/new" in branches.stdout

        # Verify HEAD is on the new branch.
        head = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            check=True,
        )
        assert head.stdout.strip() == "feat/new"

    def test_checkout_existing(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)

        # Create a branch manually first.
        subprocess.run(
            ["git", "checkout", "-b", "feat/existing"],
            cwd=str(tmp_path),
            capture_output=True,
            check=True,
        )
        # Go back to main/master.
        subprocess.run(
            ["git", "checkout", "-"],
            cwd=str(tmp_path),
            capture_output=True,
            check=True,
        )

        # Use checkout_only to switch to the existing branch.
        result = GitBranchTool().execute(
            name="feat/existing", checkout_only=True, path=str(tmp_path)
        )
        assert result.success
        assert result.data["branch"] == "feat/existing"


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
