"""Split from ``test_checkpoint.py``."""

from __future__ import annotations

from pathlib import Path

from axm_edit.core.checkpoint import create_checkpoint, rollback


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
