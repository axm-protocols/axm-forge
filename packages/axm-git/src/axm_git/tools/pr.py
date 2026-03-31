"""GitPRTool — create GitHub pull requests via gh CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

from axm_git.core.runner import gh_available, not_a_repo_error, run_gh, run_git

__all__ = ["GitPRTool"]


class GitPRTool(AXMTool):
    """Create a GitHub pull request with optional auto-merge.

    Registered as ``git_pr`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "git_pr"

    def execute(  # type: ignore[override]  # Tool accepts specific args instead of generic kwargs
        self,
        *,
        title: str,
        body: str | None = None,
        base: str = "main",
        auto_merge: bool = True,
        path: str = ".",
        **kwargs: Any,
    ) -> ToolResult:
        """Create a GitHub pull request.

        Args:
            title: PR title (required).
            body: PR body/description.
            base: Base branch (default ``main``).
            auto_merge: Enable auto-merge with squash (default ``True``).
            path: Repository path.

        Returns:
            ToolResult with ``pr_url`` and ``pr_number`` on success.
        """
        resolved = Path(path).resolve()

        # 1. Verify this is a git repo.
        check = run_git(["rev-parse", "--git-dir"], resolved)
        if check.returncode != 0:
            return not_a_repo_error(check.stderr, resolved)

        # 2. Check gh availability.
        if not gh_available():
            return ToolResult(
                success=False,
                error="gh CLI not available",
            )

        # 3. Create the PR.
        create_args = ["pr", "create", "--title", title, "--base", base]
        if body:
            create_args.extend(["--body", body])

        result = run_gh(create_args, resolved)
        if result.returncode != 0:
            return ToolResult(
                success=False,
                error=result.stderr.strip() or result.stdout.strip(),
            )

        pr_url = result.stdout.strip()
        pr_number = pr_url.rstrip("/").rsplit("/", maxsplit=1)[-1]

        # 4. Enable auto-merge if requested.
        if auto_merge:
            merge_result = run_gh(
                ["pr", "merge", pr_number, "--auto", "--squash"],
                resolved,
            )
            return ToolResult(
                success=True,
                data={
                    "pr_url": pr_url,
                    "pr_number": pr_number,
                    "auto_merge": merge_result.returncode == 0,
                },
            )

        return ToolResult(
            success=True,
            data={
                "pr_url": pr_url,
                "pr_number": pr_number,
                "auto_merge": False,
            },
        )
