"""GitAwaitMergeTool — poll a GitHub PR until it is merged or times out."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from axm.tools.base import AXMTool, ToolResult

from axm_git.core.runner import gh_available, run_gh, timeout_error_result
from axm_git.tools.await_merge_text import render_failure_text, render_text

__all__ = ["GitAwaitMergeTool"]

_DEFAULT_TIMEOUT = 600  # 10 minutes
_DEFAULT_INTERVAL = 30  # seconds


class GitAwaitMergeTool(AXMTool):
    """Poll a GitHub PR until it reaches the ``MERGED`` state.

    Blocks, querying ``gh pr view --json state`` every *interval* seconds
    until the PR is merged, is closed, or *timeout* elapses. Registered as
    ``git_await_merge`` via axm.tools entry point.
    """

    domain = "git"
    tags = frozenset({"pr", "merge", "poll", "await"})

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "git_await_merge"

    def execute(  # type: ignore[override]
        self,
        *,
        pr: str,
        timeout: int = _DEFAULT_TIMEOUT,
        interval: int = _DEFAULT_INTERVAL,
        path: str = ".",
        **kwargs: object,
    ) -> ToolResult:
        """Poll PR *pr* until merged or timed out.

        Args:
            pr: PR number or URL (required).
            timeout: Maximum seconds to wait (default 600).
            interval: Seconds between polls (default 30).
            path: Repository path.

        Returns:
            ToolResult with ``merged=True`` and ``pr_ref`` on success.
        """
        resolved = Path(path).resolve()
        if not gh_available():
            error = "gh CLI not available"
            return ToolResult(
                success=False, error=error, text=render_failure_text(error=error)
            )

        try:
            start = time.monotonic()
            while time.monotonic() - start < timeout:
                state = _poll_pr_state(pr, resolved)
                if state is None:
                    error = f"failed to query PR {pr} state"
                    return ToolResult(
                        success=False,
                        error=error,
                        text=render_failure_text(error=error),
                    )
                if state == "MERGED":
                    data: dict[str, object] = {"merged": True, "pr_ref": pr}
                    return ToolResult(success=True, data=data, text=render_text(data))
                if state == "CLOSED":
                    error = f"PR {pr} was closed without merging"
                    return ToolResult(
                        success=False,
                        error=error,
                        text=render_failure_text(error=error),
                    )
                time.sleep(interval)
        except subprocess.TimeoutExpired as exc:
            return timeout_error_result(exc)

        error = f"PR {pr} not merged after {timeout}s timeout"
        return ToolResult(
            success=False, error=error, text=render_failure_text(error=error)
        )


def _poll_pr_state(pr_ref: str, working_dir: Path) -> str | None:
    """Query the current state of a PR (``OPEN``/``MERGED``/``CLOSED``)."""
    result = run_gh(["pr", "view", pr_ref, "--json", "state"], working_dir)
    if result.returncode != 0:
        return None
    try:
        state = json.loads(result.stdout)["state"]
    except (json.JSONDecodeError, KeyError):
        return None
    return state if isinstance(state, str) else None
