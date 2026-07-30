"""Split from ``test_runner.py``."""

from __future__ import annotations

from pathlib import Path

from axm_git.core.runner import not_a_repo_error


class TestNotARepoError:
    """Test not_a_repo_error helper."""

    def test_with_suggestions(self, tmp_path: Path) -> None:
        """Non-git dir with git children → error includes suggestions."""
        (tmp_path / "axm-core" / ".git").mkdir(parents=True)
        (tmp_path / "axm-ast" / ".git").mkdir(parents=True)
        result = not_a_repo_error("fatal: not a git repository", tmp_path)
        assert not result.success
        assert "not a git repository" in (result.error or "")
        assert result.data is not None
        assert result.data["suggestions"] == ["axm-ast", "axm-core"]

    def test_no_suggestions(self, tmp_path: Path) -> None:
        """Non-git dir with no git children → standard error."""
        result = not_a_repo_error("fatal: not a git repository", tmp_path)
        assert not result.success
        assert "not a git repository" in (result.error or "")
        assert result.data is None or "suggestions" not in result.data

    def test_other_error_passthrough(self, tmp_path: Path) -> None:
        """Non 'not a git repository' error → standard error, no scanning."""
        (tmp_path / "axm-core" / ".git").mkdir(parents=True)
        result = not_a_repo_error("fatal: some other error", tmp_path)
        assert not result.success
        assert "some other error" in (result.error or "")
        # Should NOT scan for repos on unrelated errors
        assert result.data is None or "suggestions" not in result.data
