"""Preflight hook action.

Runs ``git status --porcelain`` and ``git diff -U2`` to report
working-tree state before a protocol phase.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm.hooks.base import HookResult

from axm_git.core.runner import find_git_root, run_git
from axm_git.hooks._resolve import _resolve_working_dir
from axm_git.tools.commit_preflight import _render_text

__all__ = ["PreflightHook", "_truncate_diff"]

_MIN_STATUS_LINE_LEN = 4  # git porcelain format: "XY filename"


def _truncate_diff(stdout: str, max_lines: int) -> str:
    """Truncate diff output to *max_lines*.

    Returns the first *max_lines* lines joined by newlines,
    or the stripped original when it fits.  Returns an empty
    string when *max_lines* is ``0``.
    """
    if max_lines <= 0:
        return ""
    lines = stdout.splitlines()
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines])
    return stdout.strip()


def _compute_pathspec(working_dir: Path, git_root: Path) -> list[str]:
    """Build the ``["--", rel]`` pathspec scoping git commands to the package.

    Returns an empty list when *working_dir* is the git root itself.
    """
    rel = working_dir.resolve().relative_to(git_root.resolve())
    return ["--", str(rel)] if str(rel) != "." else []


def _collect_status_files(status_stdout: str) -> list[dict[str, str]]:
    """Parse ``git status --porcelain`` output into ``{path, status}`` rows."""
    files: list[dict[str, str]] = []
    for line in status_stdout.splitlines():
        if len(line) < _MIN_STATUS_LINE_LEN:
            continue
        files.append({"path": line[3:], "status": line[:2].strip()})
    return files


def _collect_diff_stat(git_root: Path, pathspec: list[str]) -> str:
    """Run ``git diff --stat`` and return its trimmed stdout (empty on failure)."""
    result = run_git(["diff", "--stat", *pathspec], git_root)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _collect_diff(
    git_root: Path, pathspec: list[str], max_diff_lines: int
) -> tuple[str, bool]:
    """Run ``git diff -U2`` and return ``(truncated_text, was_truncated)``.

    Returns ``("", False)`` when *max_diff_lines* is non-positive.
    """
    if max_diff_lines <= 0:
        return "", False
    result = run_git(["diff", "-U2", *pathspec], git_root)
    raw_lines = result.stdout.splitlines()
    truncated = _truncate_diff(result.stdout, max_diff_lines)
    return truncated, len(raw_lines) > max_diff_lines


@dataclass
class PreflightHook:
    """Report working-tree status and diff as a pre-hook.

    Designed for injection into protocol briefings via
    ``inject_result`` + ``inline: true``.

    *params*:
        ``path`` — project root (default ``"."``).
        ``diff_lines`` — max diff lines (default 200, 0 to disable).
    """

    def execute(self, context: dict[str, Any], **params: Any) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary.
            **params: Optional ``path`` and ``diff_lines``.

        Returns:
            HookResult with a compact ``text`` render (via ``_render_text``)
            and metadata containing ``files``, ``diff``, ``file_count``,
            and ``clean``.
        """
        if not params.get("enabled", True):
            return HookResult.ok(skipped=True, reason="git disabled")

        working_dir = _resolve_working_dir(params, context, param_key="path").resolve()
        max_diff_lines: int = int(params.get("diff_lines", 200))

        git_root = find_git_root(working_dir)
        if git_root is None:
            return HookResult.ok(skipped=True, reason="not a git repo")

        pathspec = _compute_pathspec(working_dir, git_root)

        status = run_git(["status", "--porcelain", *pathspec], git_root)
        if status.returncode != 0:
            return HookResult.fail(f"git status failed: {status.stderr}")

        files = _collect_status_files(status.stdout)
        diff_stat_out = _collect_diff_stat(git_root, pathspec)
        diff_content, diff_truncated = _collect_diff(git_root, pathspec, max_diff_lines)

        rendered = _render_text(
            files=files,
            diff_stat=diff_stat_out,
            diff=diff_content,
            diff_truncated=diff_truncated,
            max_diff_lines=max_diff_lines,
        )

        return HookResult(
            success=True,
            text=rendered,
            metadata={
                "files": files,
                "diff": diff_content,
                "file_count": len(files),
                "clean": len(files) == 0,
            },
        )
