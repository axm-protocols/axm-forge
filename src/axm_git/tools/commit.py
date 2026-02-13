"""GitCommitTool — batched atomic commits with pre-commit handling."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

from axm_git.core.runner import run_git

__all__ = ["GitCommitTool"]


class GitCommitTool(AXMTool):
    """Execute one or more atomic commits in a single call.

    Each commit in the batch is processed sequentially: stage files,
    run ``git commit`` (pre-commit hooks fire automatically), and
    capture the result.  If a commit fails (e.g. pre-commit rejects),
    processing stops and the error is returned alongside any commits
    that already succeeded.

    Registered as ``git_commit`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "git_commit"

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute batched commits.

        Args:
            **kwargs: Keyword arguments.
                path: Project root (required).
                commits: List of commit specs, each a dict with keys:
                    - ``files`` (list[str]): Files to stage.
                    - ``message`` (str): Commit summary line.
                    - ``body`` (str, optional): Commit body.

        Returns:
            ToolResult with list of committed results.
        """
        path = Path(kwargs.get("path", ".")).resolve()
        commits: list[dict[str, Any]] = kwargs.get("commits", [])

        if not commits:
            return ToolResult(
                success=False,
                error="No commits provided",
            )

        results: list[dict[str, Any]] = []

        for i, spec in enumerate(commits):
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
            add = run_git(["add", *files], path)
            if add.returncode != 0:
                return ToolResult(
                    success=False,
                    error=f"Commit {i + 1}: git add failed: {add.stderr.strip()}",
                    data={"results": results, "succeeded": len(results)},
                )

            # Build commit command
            commit_args = ["commit", "-m", message]
            if body:
                commit_args.extend(["-m", body])

            # Attempt commit (pre-commit hooks run automatically)
            commit = run_git(commit_args, path)

            if commit.returncode != 0:
                output = commit.stdout + commit.stderr

                # Detect auto-fixed files
                auto_fixed: list[str] = []
                if "files were modified by this hook" in output:
                    # Check which staged files were modified
                    diff = run_git(["diff", "--name-only"], path)
                    auto_fixed = [
                        f for f in diff.stdout.strip().splitlines() if f.strip()
                    ]

                return ToolResult(
                    success=False,
                    error=f"Commit {i + 1}: pre-commit failed",
                    data={
                        "results": results,
                        "succeeded": len(results),
                        "failed_commit": {
                            "index": i + 1,
                            "message": message,
                            "precommit_output": output.strip(),
                            "auto_fixed_files": auto_fixed,
                        },
                    },
                )

            # Get the SHA of the commit
            log = run_git(["log", "-1", "--format=%H"], path)
            sha = log.stdout.strip()[:7]

            results.append(
                {
                    "sha": sha,
                    "message": message,
                    "precommit_passed": True,
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
