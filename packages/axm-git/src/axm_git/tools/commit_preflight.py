"""GitPreflightTool — show working tree status for agent decision-making."""

from __future__ import annotations

import subprocess
from pathlib import Path

from axm.tools.base import AXMTool, ToolResult

from axm_git.core.runner import (
    find_git_root,
    not_a_repo_error,
    run_git,
    timeout_error_result,
)

__all__ = ["GitPreflightTool", "render_text"]

_MIN_STATUS_LINE_LEN = 4  # git porcelain format: "XY filename"
_STATUS_PAD = 3  # pad status codes to 3 chars (e.g. "M  ", "?? ")


def render_text(
    *,
    files: list[dict[str, str]],
    diff_stat: str,
    diff: str,
    diff_truncated: bool,
    max_diff_lines: int,
) -> str:
    """Render a compact text summary of preflight results."""
    if not files:
        return "git_preflight | clean"

    parts: list[str] = [f"git_preflight | {len(files)} files · dirty", ""]

    for f in files:
        status = f["status"]
        parts.append(f"{status:<{_STATUS_PAD}}{f['path']}")

    if diff_stat:
        parts.append("")
        parts.append(diff_stat)

    if diff:
        parts.append("")
        parts.append(diff)

    if diff_truncated:
        parts.append(f"[diff truncated at {max_diff_lines} lines]")

    return "\n".join(parts)


def _resolve_scope(resolved: Path) -> tuple[list[str], Path]:
    """Return (pathspec, cwd) scoping git to the resolved subdirectory."""
    git_root = find_git_root(resolved)
    if git_root is None:
        # Not a repo (or find_git_root failed) — fall through with resolved
        # so run_git triggers not_a_repo_error naturally.
        return [], resolved
    rel = resolved.relative_to(git_root.resolve())
    pathspec = ["--", str(rel)] if str(rel) != "." else []
    return pathspec, git_root


def _parse_status(stdout: str) -> list[dict[str, str]]:
    """Parse ``git status --porcelain`` output into file entries."""
    files: list[dict[str, str]] = []
    for line in stdout.splitlines():
        if len(line) < _MIN_STATUS_LINE_LEN:
            continue
        files.append({"path": line[3:], "status": line[:2].strip()})
    return files


def _collect_diff(
    pathspec: list[str], cwd: Path, max_diff_lines: int
) -> tuple[str, bool]:
    """Return (diff_content, truncated) for ``git diff -U2``."""
    if max_diff_lines <= 0:
        return "", False
    diff_result = run_git(["diff", "-U2", *pathspec], cwd)
    lines = diff_result.stdout.splitlines()
    if len(lines) > max_diff_lines:
        return "\n".join(lines[:max_diff_lines]), True
    return diff_result.stdout.strip(), False


class GitPreflightTool(AXMTool):
    """Report working tree changes so the agent can plan commits.

    Registered as ``git_preflight`` via axm.tools entry point.
    """

    expose_directly = True
    domain = "git"
    tags = frozenset({"status", "diff", "preflight"})

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "git_preflight"

    def execute(
        self,
        *,
        path: str = ".",
        diff_lines: int = 200,
        **kwargs: object,
    ) -> ToolResult:
        """Show current working tree status and diff summary.

        Args:
            path: Project root (required).
            diff_lines: Max diff lines to include (default 200, 0 to
                disable).

        Returns:
            ToolResult with file list, statuses, diff stats, and diff content.
        """
        resolved = Path(path).resolve()
        max_diff_lines = diff_lines

        try:
            pathspec, cwd = _resolve_scope(resolved)

            status = run_git(["status", "--porcelain", *pathspec], cwd)
            if status.returncode != 0:
                return not_a_repo_error(status.stderr, resolved)
            files = _parse_status(status.stdout)

            # git diff --stat [-- rel_path] (only when dirty)
            diff_stat_out = ""
            if files:
                diff_stat_out = run_git(
                    ["diff", "--stat", *pathspec], cwd
                ).stdout.strip()

            diff_content, diff_truncated = _collect_diff(pathspec, cwd, max_diff_lines)
        except subprocess.TimeoutExpired as exc:
            return timeout_error_result(exc)

        text = render_text(
            files=files,
            diff_stat=diff_stat_out,
            diff=diff_content,
            diff_truncated=diff_truncated,
            max_diff_lines=max_diff_lines,
        )

        return ToolResult(
            success=True,
            data={
                "files": files,
                "file_count": len(files),
                "diff_stat": diff_stat_out,
                "diff": diff_content,
                "diff_truncated": diff_truncated,
                "clean": len(files) == 0,
            },
            text=text,
        )
