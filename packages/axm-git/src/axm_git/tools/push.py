"""GitPushTool — push current branch with dirty-check and upstream detection."""

from __future__ import annotations

import subprocess
from pathlib import Path

from axm.tools.base import AXMTool, ToolResult

from axm_git.core.runner import (
    not_a_repo_error,
    parse_porcelain_z,
    run_git,
    timeout_error_result,
)
from axm_git.tools.push_text import render_failure_text, render_text

__all__ = ["GitPushTool"]


def _check_dirty(resolved: Path) -> ToolResult | None:
    """Return a failure ToolResult if the tree is dirty, else None."""
    status = run_git(["status", "--porcelain", "-z"], resolved)
    if status.returncode != 0:
        error = status.stderr.strip()
        return ToolResult(
            success=False,
            error=error,
            text=render_failure_text(error=error, data=None),
        )
    dirty_files = [row["path"] for row in parse_porcelain_z(status.stdout)]
    if dirty_files:
        error = "Working tree is dirty. Commit or stash changes first."
        data: dict[str, object] = {"dirty_files": dirty_files}
        return ToolResult(
            success=False,
            error=error,
            data=data,
            text=render_failure_text(error=error, data=data),
        )
    return None


def _resolve_force_flag(*, force: bool, force_unconditional: bool) -> str | None:
    """Resolve the force-push argv flag.

    Returns ``--force-with-lease`` for a safe force (the default), bare
    ``--force`` only when ``force_unconditional`` is set, or ``None`` for
    a non-force push.
    """
    if not force:
        return None
    return "--force" if force_unconditional else "--force-with-lease"


def _build_push_cmd(
    *,
    force_flag: str | None,
    has_upstream: bool,
    set_upstream: bool,
    remote: str,
    branch: str,
) -> list[str]:
    """Build the ``git push`` argument list.

    ``force_flag`` is the pre-resolved force token (``--force-with-lease``,
    ``--force``, or ``None``); see :func:`_resolve_force_flag`.
    """
    cmd: list[str] = ["push"]
    if force_flag is not None:
        cmd.append(force_flag)
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
        force_unconditional: bool = False,
        **kwargs: object,
    ) -> ToolResult:
        """Push the current branch to a remote.

        Args:
            path: Project root directory.
            remote: Remote name (default ``origin``).
            set_upstream: Auto-set upstream for new branches.
            force: If True, force-push using ``--force-with-lease`` (safe:
                the remote is only overwritten if it has not advanced
                beyond our remote-tracking ref).
            force_unconditional: If True (and ``force`` is set), use a bare
                ``--force`` instead, overwriting the remote unconditionally.
                DATA-LOSS RISK: this discards remote commits we never saw.
                Leave False unless a deliberate hard overwrite is intended.

        Returns:
            ToolResult with branch, remote, and push status.
        """
        resolved = Path(path).resolve()

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

            # 2. Dirty check.
            dirty_err = _check_dirty(resolved)
            if dirty_err is not None:
                return dirty_err

            # 3. Get current branch.
            branch_result = run_git(["branch", "--show-current"], resolved)
            branch = branch_result.stdout.strip()
            if not branch:
                error = "No branch checked out (detached HEAD)."
                return ToolResult(
                    success=False,
                    error=error,
                    text=render_failure_text(error=error, data=None),
                )

            # 4. Detect upstream.
            upstream = run_git(
                ["rev-parse", "--abbrev-ref", "@{u}"],
                resolved,
            )
            has_upstream = upstream.returncode == 0

            # 5. Push.
            force_flag = _resolve_force_flag(
                force=force, force_unconditional=force_unconditional
            )
            cmd = _build_push_cmd(
                force_flag=force_flag,
                has_upstream=has_upstream,
                set_upstream=set_upstream,
                remote=remote,
                branch=branch,
            )
            push_result = run_git(cmd, resolved)
            if push_result.returncode != 0:
                error = push_result.stderr.strip() or push_result.stdout.strip()
                return ToolResult(
                    success=False,
                    error=error,
                    text=render_failure_text(error=error, data=None),
                )
        except subprocess.TimeoutExpired as exc:
            return timeout_error_result(exc)

        force_mode = force_flag.removeprefix("--") if force_flag else None
        data: dict[str, object] = {
            "branch": branch,
            "remote": remote,
            "pushed": True,
            "set_upstream": not has_upstream and set_upstream,
            "force_mode": force_mode,
        }
        return ToolResult(success=True, data=data, text=render_text(data))
