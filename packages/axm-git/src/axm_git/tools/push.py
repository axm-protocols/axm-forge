"""GitPushTool — push current branch with dirty-check and upstream detection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

from axm_git.core.runner import not_a_repo_error, run_git

__all__ = ["GitPushTool"]

_MIN_STATUS_LINE_LEN = 4  # git porcelain format: "XY filename"


def _check_dirty(resolved: Path) -> ToolResult | None:
    """Return a failure ToolResult if the tree is dirty, else None."""
    status = run_git(["status", "--porcelain"], resolved)
    if status.returncode != 0:
        return ToolResult(success=False, error=status.stderr.strip())
    dirty_files = [
        line[3:]
        for line in status.stdout.splitlines()
        if len(line) >= _MIN_STATUS_LINE_LEN
    ]
    if dirty_files:
        return ToolResult(
            success=False,
            error="Working tree is dirty. Commit or stash changes first.",
            data={"dirty_files": dirty_files},
        )
    return None


def _build_push_cmd(
    *,
    force: bool,
    has_upstream: bool,
    set_upstream: bool,
    remote: str,
    branch: str,
) -> list[str]:
    """Build the ``git push`` argument list."""
    cmd: list[str] = ["push"]
    if force:
        cmd.append("--force")
    if not has_upstream and set_upstream:
        cmd.extend(["--set-upstream", remote, branch])
    else:
        cmd.extend([remote, branch])
    return cmd


class GitPushTool(AXMTool):
    """Push the current branch after verifying a clean working tree.

    Registered as ``git_push`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "git_push"

    def execute(
        self,
        *,
        path: str = ".",
        remote: str = "origin",
        set_upstream: bool = True,
        force: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        """Push the current branch to a remote.

        Args:
            path: Project root directory.
            remote: Remote name (default ``origin``).
            set_upstream: Auto-set upstream for new branches.
            force: If True, force-push.

        Returns:
            ToolResult with branch, remote, and push status.
        """
        resolved = Path(path).resolve()

        # 1. Verify this is a git repo.
        check = run_git(["rev-parse", "--git-dir"], resolved)
        if check.returncode != 0:
            return not_a_repo_error(check.stderr, resolved)

        # 2. Dirty check.
        dirty_err = _check_dirty(resolved)
        if dirty_err is not None:
            return dirty_err

        # 3. Get current branch.
        branch_result = run_git(["branch", "--show-current"], resolved)
        branch = branch_result.stdout.strip()
        if not branch:
            return ToolResult(
                success=False,
                error="No branch checked out (detached HEAD).",
            )

        # 4. Detect upstream.
        upstream = run_git(
            ["rev-parse", "--abbrev-ref", "@{u}"],
            resolved,
        )
        has_upstream = upstream.returncode == 0

        # 5. Push.
        cmd = _build_push_cmd(
            force=force,
            has_upstream=has_upstream,
            set_upstream=set_upstream,
            remote=remote,
            branch=branch,
        )
        push_result = run_git(cmd, resolved)
        if push_result.returncode != 0:
            return ToolResult(
                success=False,
                error=(push_result.stderr.strip() or push_result.stdout.strip()),
            )

        return ToolResult(
            success=True,
            data={
                "branch": branch,
                "remote": remote,
                "pushed": True,
                "set_upstream": not has_upstream and set_upstream,
            },
        )
