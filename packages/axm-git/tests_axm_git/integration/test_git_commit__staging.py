"""Integration tests for git_commit internal staging (``git add -A -- <path>``).

Exercises the module-local staging helper through the public
:class:`~axm_git.tools.commit.GitCommitTool` surface against real temporary git
repositories (no subprocess mocking). Covers deletions staged via ``git rm``,
plain disk deletions, whole-directory deletions, and the add/modify
non-regression path.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_git.tools.commit import GitCommitTool

pytestmark = pytest.mark.integration


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a git command in *cwd*."""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _init_repo(tmp_path: Path) -> Path:
    """Create a real git repo with identity and an initial commit."""
    _git(["init", "-q", "-b", "main"], tmp_path)
    _git(["config", "user.email", "test@example.com"], tmp_path)
    _git(["config", "user.name", "Test"], tmp_path)
    _git(["config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / "README.md").write_text("init\n")
    _git(["add", "-A"], tmp_path)
    _git(["commit", "-q", "-m", "chore: init"], tmp_path)
    return tmp_path


def _tracked(repo: Path) -> set[str]:
    """Return the set of paths present in the HEAD tree."""
    result = _git(["ls-tree", "-r", "--name-only", "HEAD"], repo)
    return {line for line in result.stdout.splitlines() if line}


def _commit_count(repo: Path) -> int:
    """Return the number of commits reachable from HEAD."""
    return int(_git(["rev-list", "--count", "HEAD"], repo).stdout.strip())


def test_git_rm_staged_file_deletion_is_committed(tmp_path: Path) -> None:
    """AC2: a spec listing a ``git rm``-staged file commits the deletion."""
    repo = _init_repo(tmp_path)
    (repo / "gone.py").write_text("bye\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "feat: add gone.py"], repo)
    assert "gone.py" in _tracked(repo)

    _git(["rm", "-q", "gone.py"], repo)
    before = _commit_count(repo)

    result = GitCommitTool().execute(
        path=str(repo),
        commits=[{"files": ["gone.py"], "message": "chore: remove gone.py"}],
    )

    assert result.success is True, result.error
    assert "gone.py" not in _tracked(repo)
    assert _commit_count(repo) == before + 1


def test_disk_deleted_file_deletion_is_committed(tmp_path: Path) -> None:
    """AC2: a spec listing a disk-deleted file (no ``git rm``) commits it."""
    repo = _init_repo(tmp_path)
    (repo / "vanish.py").write_text("data\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "feat: add vanish.py"], repo)

    (repo / "vanish.py").unlink()

    result = GitCommitTool().execute(
        path=str(repo),
        commits=[{"files": ["vanish.py"], "message": "chore: drop vanish.py"}],
    )

    assert result.success is True, result.error
    assert "vanish.py" not in _tracked(repo)
    show = _git(["show", "--name-status", "--format=", "HEAD"], repo)
    assert "D\tvanish.py" in show.stdout


def test_whole_deleted_directory_deletion_is_committed(tmp_path: Path) -> None:
    """AC3: a spec listing a wholly removed directory commits every deletion."""
    repo = _init_repo(tmp_path)
    pkg = repo / "pkg"
    pkg.mkdir()
    for name in ("a.py", "b.py", "c.py"):
        (pkg / name).write_text(f"content {name}\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "feat: add pkg"], repo)
    assert {"pkg/a.py", "pkg/b.py", "pkg/c.py"} <= _tracked(repo)

    for name in ("a.py", "b.py", "c.py"):
        (pkg / name).unlink()
    pkg.rmdir()

    result = GitCommitTool().execute(
        path=str(repo),
        commits=[{"files": ["pkg"], "message": "chore: remove pkg"}],
    )

    assert result.success is True, result.error
    tracked = _tracked(repo)
    assert not any(p.startswith("pkg/") for p in tracked)


def test_added_and_modified_files_still_commit(tmp_path: Path) -> None:
    """AC4: add + modify spec commits unchanged (1 commit, all paths present)."""
    repo = _init_repo(tmp_path)
    (repo / "existing.py").write_text("v1\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "feat: add existing.py"], repo)

    # One brand-new file plus a modification of a tracked file.
    (repo / "new.py").write_text("fresh\n")
    (repo / "existing.py").write_text("v2\n")
    before = _commit_count(repo)

    result = GitCommitTool().execute(
        path=str(repo),
        commits=[{"files": ["new.py", "existing.py"], "message": "feat: add + modify"}],
    )

    assert result.success is True, result.error
    assert _commit_count(repo) == before + 1
    tracked = _tracked(repo)
    assert {"new.py", "existing.py"} <= tracked
