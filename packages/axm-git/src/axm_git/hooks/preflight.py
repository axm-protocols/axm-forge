"""Preflight hook action.

Runs ``git status --porcelain`` and ``git diff -U2`` to report
working-tree state before a protocol phase.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm.hooks.base import HookResult

from axm_git.core.runner import run_git

__all__ = ["PreflightHook"]

_MIN_STATUS_LINE_LEN = 4  # git porcelain format: "XY filename"


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
            HookResult with ``files``, ``diff``, ``file_count``, and ``clean``.
        """
        if not params.get("enabled", True):
            return HookResult.ok(skipped=True, reason="git disabled")

        path = params.get("path", context.get("working_dir", "."))
        working_dir = Path(path).resolve()
        max_diff_lines: int = int(params.get("diff_lines", 200))

        if not (working_dir / ".git").exists():
            return HookResult.ok(skipped=True, reason="not a git repo")

        # git status --porcelain
        status = run_git(["status", "--porcelain"], working_dir)
        if status.returncode != 0:
            return HookResult.fail(f"git status failed: {status.stderr}")

        files: list[dict[str, str]] = []
        for line in status.stdout.splitlines():
            if len(line) < _MIN_STATUS_LINE_LEN:
                continue
            code = line[:2].strip()
            filepath = line[3:]
            files.append({"path": filepath, "status": code})

        # git diff -U2
        diff_content = ""
        if max_diff_lines > 0:
            diff_result = run_git(["diff", "-U2"], working_dir)
            lines = diff_result.stdout.splitlines()
            if len(lines) > max_diff_lines:
                diff_content = "\n".join(lines[:max_diff_lines])
            else:
                diff_content = diff_result.stdout.strip()

        return HookResult.ok(
            files=files,
            diff=diff_content,
            file_count=len(files),
            clean=len(files) == 0,
        )
