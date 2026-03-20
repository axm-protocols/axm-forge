"""Unit tests for the runner module."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from axm_git.core.runner import (
    detect_package_name,
    find_git_root,
    gh_available,
    not_a_repo_error,
    run_gh,
    run_git,
    suggest_git_repos,
)


class TestRunGit:
    """Test run_git helper."""

    def test_success(self, tmp_path: Path) -> None:
        run_git(["init"], tmp_path)
        result = run_git(["status", "--short"], tmp_path)
        assert result.returncode == 0

    def test_failure_bad_dir(self, tmp_path: Path) -> None:
        result = run_git(["status"], tmp_path)
        assert result.returncode != 0

    def test_defaults(self, tmp_path: Path) -> None:
        """Verify default kwargs are applied."""
        run_git(["init"], tmp_path)
        result = run_git(["status"], tmp_path)
        # text=True → stdout is str
        assert isinstance(result.stdout, str)


class TestGhAvailable:
    """Test gh_available helper."""

    @patch("axm_git.core.runner.shutil.which", return_value=None)
    def test_gh_not_installed(self, _which: MagicMock) -> None:
        assert gh_available() is False

    @patch("axm_git.core.runner.subprocess.run")
    @patch("axm_git.core.runner.shutil.which", return_value="/usr/bin/gh")
    def test_gh_installed_auth_ok(self, _which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh"], returncode=0, stdout="", stderr=""
        )
        assert gh_available() is True

    @patch("axm_git.core.runner.subprocess.run")
    @patch("axm_git.core.runner.shutil.which", return_value="/usr/bin/gh")
    def test_gh_installed_auth_fail(
        self, _which: MagicMock, mock_run: MagicMock
    ) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh"], returncode=1, stdout="", stderr="not logged in"
        )
        assert gh_available() is False


class TestRunGh:
    """Test run_gh helper."""

    @patch("axm_git.core.runner.subprocess.run")
    def test_run_gh_delegates(self, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh"], returncode=0, stdout="ok", stderr=""
        )
        result = run_gh(["auth", "status"], Path("/tmp"))
        assert result.returncode == 0
        assert result.stdout == "ok"
        mock_run.assert_called_once()


class TestDetectPackageName:
    """Test detect_package_name helper."""

    def test_valid_pyproject(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "my-pkg"\n')
        assert detect_package_name(tmp_path) == "my-pkg"

    def test_missing_pyproject(self, tmp_path: Path) -> None:
        assert detect_package_name(tmp_path) is None

    def test_no_project_section(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[build-system]\n")
        assert detect_package_name(tmp_path) is None

    def test_invalid_toml(self, tmp_path: Path) -> None:
        """Malformed TOML returns None via exception handler."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("{{invalid toml}}")
        assert detect_package_name(tmp_path) is None


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
        """Non \'not a git repository\' error → standard error, no scanning."""
        (tmp_path / "axm-core" / ".git").mkdir(parents=True)
        result = not_a_repo_error("fatal: some other error", tmp_path)
        assert not result.success
        assert "some other error" in (result.error or "")
        # Should NOT scan for repos on unrelated errors
        assert result.data is None or "suggestions" not in result.data


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
