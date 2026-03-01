"""GitHub Adapter — interact with GitHub via gh CLI.

Provides repository creation, secret management, and Pages setup
using the GitHub CLI (gh) for authentication and operations.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class RepoCreateResult:
    """Result of repository creation."""

    success: bool
    url: str
    message: str


class GitHubAdapter:
    """Adapter for GitHub operations via gh CLI.

    All operations require gh to be installed and authenticated.
    """

    def check_installed(self) -> bool:
        """Check if gh CLI is installed.

        Returns:
            True if gh is available.
        """
        try:
            result = subprocess.run(
                ["gh", "--version"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def check_auth(self) -> bool:
        """Check if user is authenticated with gh.

        Returns:
            True if authenticated.
        """
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def create_repo(
        self,
        name: str,
        org: str | None = None,
        private: bool = False,
        push_source: bool = True,
    ) -> RepoCreateResult:
        """Create a GitHub repository.

        Args:
            name: Repository name.
            org: Organization (None for personal account).
            private: Create as private repo.
            push_source: Push current directory as source.

        Returns:
            RepoCreateResult with success status.
        """
        repo_name = f"{org}/{name}" if org else name
        visibility = "--private" if private else "--public"

        cmd = ["gh", "repo", "create", repo_name, visibility]
        if push_source:
            cmd.extend(["--source", ".", "--push"])

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            url = result.stdout.strip() or f"https://github.com/{repo_name}"
            return RepoCreateResult(
                success=True,
                url=url,
                message=f"Repository created: {url}",
            )

        return RepoCreateResult(
            success=False,
            url="",
            message=result.stderr.strip() or "Failed to create repository",
        )

    def set_secret(self, repo: str, name: str, value: str) -> bool:
        """Set a repository secret.

        Args:
            repo: Repository in org/name format.
            name: Secret name.
            value: Secret value.

        Returns:
            True if successful.
        """
        try:
            result = subprocess.run(
                ["gh", "secret", "set", name, "--repo", repo],
                input=value,
                text=True,
                capture_output=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def enable_pages(self, repo: str) -> bool:
        """Enable GitHub Pages for a repository.

        Args:
            repo: Repository in org/name format.

        Returns:
            True if successful.
        """
        try:
            result = subprocess.run(
                [
                    "gh",
                    "api",
                    f"repos/{repo}/pages",
                    "--method",
                    "POST",
                    "--field",
                    "build_type=workflow",
                ],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
