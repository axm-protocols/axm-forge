"""GitPRTool — create GitHub pull requests via gh CLI."""

from __future__ import annotations

import subprocess
from pathlib import Path

from axm.tools.base import AXMTool, ToolResult

from axm_git.core.pr_recovery import is_already_exists, recover_existing_pr
from axm_git.core.runner import (
    gh_available,
    not_a_repo_error,
    resolve_default_branch,
    run_gh,
    run_git,
    timeout_error_result,
)
from axm_git.tools.pr_text import render_failure_text, render_text

__all__ = ["GitPRTool"]


class GitPRTool(AXMTool):
    """Create a GitHub pull request with optional auto-merge.

    Registered as ``git_pr`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "git_pr"

    def execute(  # type: ignore[override]
        self,
        *,
        title: str,
        body: str | None = None,
        base: str | None = None,
        auto_merge: bool = False,
        path: str = ".",
        **kwargs: object,
    ) -> ToolResult:
        """Create a GitHub pull request.

        Args:
            title: PR title (required).
            body: PR body/description.
            base: Base branch (default: the repo's resolved default branch).
            auto_merge: Enable auto-merge with squash (default ``False``).
            path: Repository path.

        Returns:
            ToolResult with ``pr_url`` and ``pr_number`` on success.
        """
        resolved = Path(path).resolve()
        base = base or resolve_default_branch(resolved)

        try:
            # 1. Verify this is a git repo.
            check = run_git(["rev-parse", "--git-dir"], resolved)
            if check.returncode != 0:
                repo_err = not_a_repo_error(check.stderr, resolved)
                return ToolResult(
                    success=repo_err.success,
                    error=repo_err.error,
                    data=repo_err.data,
                    text=render_failure_text(
                        error=repo_err.error or "", data=repo_err.data
                    ),
                )

            # 2. Check gh availability.
            if not gh_available():
                error = "gh CLI not available"
                return ToolResult(
                    success=False,
                    error=error,
                    text=render_failure_text(error=error, data=None),
                )

            # 3. Create the PR.
            create_args = ["pr", "create", "--title", title, "--base", base]
            if body:
                create_args.extend(["--body", body])

            result = run_gh(create_args, resolved)
            if result.returncode != 0:
                error = result.stderr.strip() or result.stdout.strip()
                if is_already_exists(error):
                    return _recovered_pr_result(resolved, error)
                return ToolResult(
                    success=False,
                    error=error,
                    text=render_failure_text(error=error, data=None),
                )

            pr_url = result.stdout.strip()
            pr_number = pr_url.rstrip("/").rsplit("/", maxsplit=1)[-1]

            # 4. Enable auto-merge if requested.
            auto_merge_ok = False
            if auto_merge:
                merge_result = run_gh(
                    ["pr", "merge", pr_number, "--auto", "--squash"],
                    resolved,
                )
                auto_merge_ok = merge_result.returncode == 0

            data: dict[str, object] = {
                "pr_url": pr_url,
                "pr_number": pr_number,
                "auto_merge": auto_merge_ok,
            }
            return ToolResult(success=True, data=data, text=render_text(data))
        except subprocess.TimeoutExpired as exc:
            return timeout_error_result(exc)


def _recovered_pr_result(resolved: Path, original_error: str) -> ToolResult:
    """Adapt an existing-PR recovery into a ``ToolResult``.

    Returns success with ``already_existed=True`` when the existing PR can be
    resolved, else preserves the original failure.
    """
    recovery = recover_existing_pr(resolved)
    if not recovery.ok:
        error = recovery.error or original_error
        return ToolResult(
            success=False,
            error=error,
            text=render_failure_text(error=error, data=None),
        )
    data: dict[str, object] = {
        "pr_url": recovery.url,
        "pr_number": recovery.number,
        "auto_merge": False,
        "already_existed": True,
    }
    return ToolResult(success=True, data=data, text=render_text(data))
