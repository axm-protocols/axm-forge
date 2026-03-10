"""GitCommitTool — batched atomic commits with pre-commit handling."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

from axm_git.core.runner import not_a_repo_error, run_git

__all__ = ["GitCommitTool"]

logger = logging.getLogger(__name__)


def _stage_files(files: list[str], path: Path) -> str | None:
    """Stage files, return error message or None on success.

    Runs ``git reset`` first to clear any stale index entries
    (e.g. from a previous failed pre-commit), then ``git add``
    to stage the current disk content.
    """
    run_git(["reset", "HEAD", "--", *files], path)
    add = run_git(["add", "-A", "--", *files], path)
    if add.returncode != 0:
        return add.stderr.strip()
    return None


def _attempt_commit(
    commit_args: list[str], files: list[str], path: Path
) -> tuple[bool, bool, str]:
    """Attempt commit with auto-retry on pre-commit fix.

    Returns:
        (success, retried, output)
    """
    commit = run_git(commit_args, path)
    retried = False

    # If pre-commit auto-fixed files, re-stage and retry once
    if commit.returncode != 0:
        output = commit.stdout + commit.stderr
        if "files were modified by this hook" in output:
            logger.warning("Pre-commit auto-fixed files, re-staging and retrying")
            run_git(["add", "-A", "--", *files], path)
            commit = run_git(commit_args, path)
            retried = True

    output = commit.stdout + commit.stderr
    return commit.returncode == 0, retried, output


def _build_failure_data(  # noqa: PLR0913
    results: list[dict[str, Any]],
    *,
    index: int,
    message: str,
    output: str,
    retried: bool,
    path: Path,
) -> dict[str, Any]:
    """Build failure data dict for a failed commit."""
    auto_fixed: list[str] = []
    if "files were modified by this hook" in output:
        diff = run_git(["diff", "--name-only"], path)
        auto_fixed = [f for f in diff.stdout.strip().splitlines() if f.strip()]

    return {
        "results": results,
        "succeeded": len(results),
        "failed_commit": {
            "index": index,
            "message": message,
            "precommit_output": output.strip(),
            "auto_fixed_files": auto_fixed,
            "retried": retried,
        },
    }


class GitCommitTool(AXMTool):
    """Execute one or more atomic commits in a single call.

    Each commit in the batch is processed sequentially: stage files,
    run ``git commit`` (pre-commit hooks fire automatically), and
    capture the result.  If a commit fails (e.g. pre-commit rejects),
    processing stops and the error is returned alongside any commits
    that already succeeded.

    When a pre-commit hook auto-fixes files (e.g. ruff ``--fix``),
    the tool automatically re-stages and retries the commit once.

    Registered as ``git_commit`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "git_commit"

    def execute(
        self,
        *,
        path: str = ".",
        commits: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute batched commits.

        Args:
            path: Project root (required).
            commits: List of commit specs, each a dict with keys:
                - ``files`` (list[str]): Files to stage.
                - ``message`` (str): Commit summary line.
                - ``body`` (str, optional): Commit body.

        Returns:
            ToolResult with list of committed results.
        """
        resolved = Path(path).resolve()
        commit_list: list[dict[str, Any]] = commits or []

        if not commit_list:
            return ToolResult(success=False, error="No commits provided")

        # Fail fast with suggestions if not a git repo
        check = run_git(["rev-parse", "--git-dir"], resolved)
        if check.returncode != 0:
            return not_a_repo_error(check.stderr, resolved)

        results: list[dict[str, Any]] = []

        for i, spec in enumerate(commit_list):
            files: list[str] = spec.get("files", [])
            message: str = spec.get("message", "")
            body: str | None = spec.get("body")

            if not files:
                return ToolResult(
                    success=False,
                    error=f"Commit {i + 1}: empty files list",
                    data={"results": results, "succeeded": len(results)},
                )

            if not message:
                return ToolResult(
                    success=False,
                    error=f"Commit {i + 1}: empty message",
                    data={"results": results, "succeeded": len(results)},
                )

            # Stage files
            add_err = _stage_files(files, resolved)
            if add_err:
                return ToolResult(
                    success=False,
                    error=f"Commit {i + 1}: git add failed: {add_err}",
                    data={"results": results, "succeeded": len(results)},
                )

            # Build commit command
            commit_args = ["commit", "-m", message]
            if body:
                commit_args.extend(["-m", body])

            # Attempt commit with auto-retry
            ok, retried, output = _attempt_commit(commit_args, files, resolved)

            if not ok:
                return ToolResult(
                    success=False,
                    error=f"Commit {i + 1}: pre-commit failed",
                    data=_build_failure_data(
                        results,
                        index=i + 1,
                        message=message,
                        output=output,
                        retried=retried,
                        path=resolved,
                    ),
                )

            # Get the SHA of the commit
            log = run_git(["log", "-1", "--format=%H"], resolved)
            sha = log.stdout.strip()[:7]

            results.append(
                {
                    "sha": sha,
                    "message": message,
                    "precommit_passed": True,
                    "retried": retried,
                }
            )

        return ToolResult(
            success=True,
            data={
                "results": results,
                "total": len(results),
                "succeeded": len(results),
            },
        )
