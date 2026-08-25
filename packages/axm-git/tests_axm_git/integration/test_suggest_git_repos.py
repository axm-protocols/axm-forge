"""Split from ``test_runner.py``."""

from __future__ import annotations

from pathlib import Path

from axm_git.core.runner import suggest_git_repos


class TestSuggestGitRepos:
    """Test suggest_git_repos helper."""

    def test_finds_repos(self, tmp_path: Path) -> None:
        """Dirs with .git/ are returned sorted; dirs without .git/ excluded."""
        (tmp_path / "beta" / ".git").mkdir(parents=True)
        (tmp_path / "alpha" / ".git").mkdir(parents=True)
        (tmp_path / "no-repo").mkdir()
        result = suggest_git_repos(tmp_path)
        assert result == ["alpha", "beta"]

    def test_in_git_repo(self, tmp_path: Path) -> None:
        """If path itself is a git repo, returns empty list."""
        (tmp_path / ".git").mkdir()
        (tmp_path / "sub" / ".git").mkdir(parents=True)
        result = suggest_git_repos(tmp_path)
        assert result == []

    def test_no_children(self, tmp_path: Path) -> None:
        """Empty directory returns empty list."""
        result = suggest_git_repos(tmp_path)
        assert result == []

    def test_permission_error(self, tmp_path: Path) -> None:
        """Unreadable subdirectory is skipped silently."""
        (tmp_path / "ok" / ".git").mkdir(parents=True)
        bad = tmp_path / "bad"
        bad.mkdir()
        bad.chmod(0o000)
        try:
            result = suggest_git_repos(tmp_path)
            assert result == ["ok"]
        finally:
            bad.chmod(0o755)
