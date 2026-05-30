"""Split from ``test_checkpoint.py``."""

from __future__ import annotations

from pathlib import Path

from axm_edit.core.checkpoint import create_checkpoint


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
