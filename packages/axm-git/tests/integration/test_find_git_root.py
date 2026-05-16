"""Split from ``test_runner.py``."""

from __future__ import annotations

from pathlib import Path

from axm_git.core.runner import find_git_root


class TestFindGitRoot:
    """Test find_git_root helper."""

    def test_at_repo_root(self, tmp_git_repo: Path) -> None:
        """Returns the repo root when called on the root itself."""
        assert find_git_root(tmp_git_repo) == tmp_git_repo

    def test_from_subdirectory(self, tmp_git_repo: Path) -> None:
        """Walks up from a subdirectory to find the repo root."""
        subdir = tmp_git_repo / "deep" / "nested"
        subdir.mkdir(parents=True)
        assert find_git_root(subdir) == tmp_git_repo

    def test_not_a_repo(self, tmp_path: Path) -> None:
        """Returns None when path is not inside any git repo."""
        assert find_git_root(tmp_path) is None
