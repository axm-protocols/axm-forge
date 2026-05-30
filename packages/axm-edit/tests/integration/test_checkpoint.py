"""Tests for axm_edit.core.checkpoint — git checkpoint and rollback."""

from __future__ import annotations

from pathlib import Path

from axm_edit.core.checkpoint import create_checkpoint, rollback


class TestCreateCheckpoint:
    """Tests for create_checkpoint."""

    def test_in_git_repo(self, git_project: Path) -> None:
        # Modify a file to have something to stash
        (git_project / "src" / "foo.py").write_text("modified\n")
        sha = create_checkpoint(git_project)
        # stash create returns a SHA when there are changes
        assert sha is not None
        assert len(sha) > 0

    def test_no_git_dir(self, tmp_project: Path) -> None:
        """Non-git directory returns None."""
        sha = create_checkpoint(tmp_project)
        assert sha is None

    def test_clean_repo_returns_none(self, git_project: Path) -> None:
        """Nothing to stash → returns None."""
        sha = create_checkpoint(git_project)
        assert sha is None


class TestRollback:
    """Tests for rollback."""

    def test_rollback_restores_file(self, git_project: Path) -> None:
        # Create checkpoint
        (git_project / "src" / "foo.py").write_text("modified\n")
        sha = create_checkpoint(git_project)
        assert sha is not None

        # Modify further
        (git_project / "src" / "foo.py").write_text("modified again\n")

        # Rollback
        success = rollback(git_project, sha)
        assert success
        # File should have the stashed content (modified version)
        restored = (git_project / "src" / "foo.py").read_text()
        assert restored == "modified\n"

    def test_rollback_removes_untracked(self, git_project: Path) -> None:
        # Create a new file
        (git_project / "src" / "new.py").write_text("new\n")

        # Rollback with empty checkpoint (just clean)
        (git_project / "src" / "foo.py").write_text("modified\n")
        sha = create_checkpoint(git_project)

        # The clean should remove untracked
        (git_project / "src" / "another.py").write_text("another\n")
        success = rollback(git_project, sha or "")
        assert success
        assert not (git_project / "src" / "another.py").exists()
