from __future__ import annotations

import subprocess
from pathlib import Path

from axm_git.hooks.commit_phase import _stage_spec_files


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
    """Create a minimal git repo with an initial commit."""
    _git(["init"], tmp_path)
    _git(["config", "user.email", "test@test.com"], tmp_path)
    _git(["config", "user.name", "Test"], tmp_path)
    (tmp_path / "init.txt").write_text("init")
    _git(["add", "init.txt"], tmp_path)
    _git(["commit", "-m", "init"], tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_deleted_tracked_file_stages_successfully(tmp_path: Path) -> None:
    """A tracked file deleted from disk should stage as a deletion."""
    repo = _init_repo(tmp_path)

    # Create, track, and commit a file, then delete it from disk
    target = repo / "deleted.py"
    target.write_text("content")
    _git(["add", "deleted.py"], repo)
    _git(["commit", "-m", "add deleted.py"], repo)
    target.unlink()

    err = _stage_spec_files(["deleted.py"], repo)
    assert err is None

    # Verify the deletion is staged
    status = _git(["diff", "--cached", "--name-only"], repo)
    assert "deleted.py" in status.stdout


def test_nonexistent_file_fails(tmp_path: Path) -> None:
    """A file that was never tracked should produce an error."""
    repo = _init_repo(tmp_path)

    err = _stage_spec_files(["never_existed.py"], repo)
    assert err is not None
    assert "never_existed.py" in err


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


def test_mixed_modified_and_deleted_files(tmp_path: Path) -> None:
    """A commit_spec with both modified and deleted files should succeed."""
    repo = _init_repo(tmp_path)

    # Create and commit two files
    (repo / "keep.py").write_text("original")
    (repo / "remove.py").write_text("to delete")
    _git(["add", "keep.py", "remove.py"], repo)
    _git(["commit", "-m", "add files"], repo)

    # Modify one, delete the other
    (repo / "keep.py").write_text("modified")
    (repo / "remove.py").unlink()

    err = _stage_spec_files(["keep.py", "remove.py"], repo)
    assert err is None

    # Both changes should be staged
    status = _git(["diff", "--cached", "--name-only"], repo)
    staged = status.stdout.strip().splitlines()
    assert "keep.py" in staged
    assert "remove.py" in staged


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_all_files_deleted(tmp_path: Path) -> None:
    """commit_spec with only deleted files should stage all deletions."""
    repo = _init_repo(tmp_path)

    # Create and commit multiple files, then delete all
    for name in ["a.py", "b.py", "c.py"]:
        (repo / name).write_text(f"content of {name}")
    _git(["add", "a.py", "b.py", "c.py"], repo)
    _git(["commit", "-m", "add files"], repo)

    for name in ["a.py", "b.py", "c.py"]:
        (repo / name).unlink()

    err = _stage_spec_files(["a.py", "b.py", "c.py"], repo)
    assert err is None

    status = _git(["diff", "--cached", "--name-only"], repo)
    staged = status.stdout.strip().splitlines()
    assert set(staged) == {"a.py", "b.py", "c.py"}


def test_deleted_then_recreated_file(tmp_path: Path) -> None:
    """A file deleted then recreated should stage normally (exists check passes)."""
    repo = _init_repo(tmp_path)

    target = repo / "revived.py"
    target.write_text("v1")
    _git(["add", "revived.py"], repo)
    _git(["commit", "-m", "add revived.py"], repo)

    # Delete then recreate with different content
    target.unlink()
    target.write_text("v2")

    err = _stage_spec_files(["revived.py"], repo)
    assert err is None

    status = _git(["diff", "--cached", "--name-only"], repo)
    assert "revived.py" in status.stdout
