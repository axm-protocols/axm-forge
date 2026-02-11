"""Tests for GitHub Adapter — RED phase."""

from unittest.mock import MagicMock, patch


class TestGitHubAdapter:
    """Tests for GitHub CLI operations."""

    def test_check_gh_installed(self) -> None:
        """Detects if gh CLI is installed."""
        from axm_init.adapters.github import GitHubAdapter

        adapter = GitHubAdapter()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert adapter.check_installed() is True

            mock_run.return_value = MagicMock(returncode=1)
            assert adapter.check_installed() is False

    def test_check_auth_status(self) -> None:
        """Checks if user is authenticated with gh."""
        from axm_init.adapters.github import GitHubAdapter

        adapter = GitHubAdapter()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert adapter.check_auth() is True

            mock_run.return_value = MagicMock(returncode=1)
            assert adapter.check_auth() is False

    def test_create_repo_success(self) -> None:
        """Creates repo and returns result."""
        from axm_init.adapters.github import GitHubAdapter

        adapter = GitHubAdapter()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="https://github.com/myorg/myrepo",
                stderr="",
            )
            result = adapter.create_repo("myrepo", org="myorg")

            assert result.success is True
            assert "myorg/myrepo" in result.url

    def test_create_repo_failure(self) -> None:
        """Handles repo creation failure."""
        from axm_init.adapters.github import GitHubAdapter

        adapter = GitHubAdapter()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Repository already exists",
            )
            result = adapter.create_repo("existing-repo", org="myorg")

            assert result.success is False
            assert "exists" in result.message.lower()

    def test_set_secret(self) -> None:
        """Sets repository secret."""
        from axm_init.adapters.github import GitHubAdapter

        adapter = GitHubAdapter()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = adapter.set_secret("myorg/myrepo", "PYPI_API_TOKEN", "pypi-xxx")

            assert result is True

    def test_enable_pages(self) -> None:
        """Enables GitHub Pages for repo."""
        from axm_init.adapters.github import GitHubAdapter

        adapter = GitHubAdapter()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = adapter.enable_pages("myorg/myrepo")

            assert result is True
