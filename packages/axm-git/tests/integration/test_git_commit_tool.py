"""Integration test for Bug 1 fix: ``auto_fixed_files`` populated correctly.

When a pre-commit hook auto-fixes files, ``data['failed_commit']
['auto_fixed_files']`` must list those files. Previously the diff was
captured *after* re-staging, which always returned an empty list.
"""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path

import pytest

from axm_git.tools.commit import GitCommitTool

pytestmark = pytest.mark.integration


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=path, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=path, check=True)


def _write_executable(target: Path, script: str) -> None:
    target.write_text(script)
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def test_auto_fixed_files_listed_when_hook_rewrites_then_fails(
    tmp_path: Path,
) -> None:
    """Hook rewrites a file and keeps failing — auto_fixed_files must list it."""
    _init_repo(tmp_path)
    target = tmp_path / "a.txt"
    target.write_text("original\n")

    hook = tmp_path / ".git" / "hooks" / "pre-commit"
    # The hook rewrites a.txt every time and exits non-zero with the
    # "files were modified by this hook" sentinel. The retry loop will
    # therefore re-stage and try again, and fail a second time. The
    # captured ``auto_fixed_files`` must contain ``a.txt``.
    _write_executable(
        hook,
        "#!/bin/sh\n"
        f'echo "rewritten" > "{target}"\n'
        'echo "files were modified by this hook" >&2\n'
        "exit 1\n",
    )

    result = GitCommitTool().execute(
        path=str(tmp_path),
        commits=[{"files": ["a.txt"], "message": "feat: add a"}],
    )

    assert result.success is False
    assert result.data is not None
    failed = result.data.get("failed_commit")
    assert failed is not None, result.data
    assert failed["retried"] is True
    assert failed["auto_fixed_files"], (
        f"expected non-empty auto_fixed_files, got {failed['auto_fixed_files']!r}"
    )
    assert "a.txt" in failed["auto_fixed_files"]


def _init_repo__from_git_commit_tool(path: Path) -> None:
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


class TestCommitFlow:
    """Functional tests for git_commit."""

    def test_commit_batch_end_to_end(self, tmp_path: Path) -> None:
        _init_repo__from_git_commit_tool(tmp_path)

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
        _init_repo__from_git_commit_tool(tmp_path)
        result = GitCommitTool().execute(
            path=str(tmp_path),
            commits=commits,
        )
        # git add on nonexistent file should fail
        assert not result.success

    def test_commit_deleted_file(self, tmp_path: Path) -> None:
        """Committing a deleted file works with git add -A."""
        _init_repo__from_git_commit_tool(tmp_path)

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
