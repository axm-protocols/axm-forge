"""GitWorktreeTool — add, remove, and list git worktrees."""

from __future__ import annotations

import subprocess
from pathlib import Path

from axm.tools.base import AXMTool, ToolResult

from axm_git.core.runner import (
    find_git_root,
    not_a_repo_error,
    resolve_default_branch,
    run_git,
    timeout_error_result,
)
from axm_git.tools.worktree_text import (
    render_add_text,
    render_failure_text,
    render_list_text,
    render_remove_text,
)

__all__ = ["GitWorktreeTool"]


def _not_a_repo_result(path: Path) -> ToolResult:
    """Build a not-a-repo ``ToolResult`` with compact failure text."""
    repo_err = not_a_repo_error("not a git repository", path)
    return ToolResult(
        success=repo_err.success,
        error=repo_err.error,
        data=repo_err.data,
        text=render_failure_text(error=repo_err.error or "", data=repo_err.data),
    )


def _git_error_result(result: subprocess.CompletedProcess[str]) -> ToolResult:
    """Build a git-command-failure ``ToolResult`` with compact failure text."""
    error = result.stderr.strip() or result.stdout.strip()
    return ToolResult(
        success=False,
        error=error,
        text=render_failure_text(error=error, data=None),
    )


_WORKTREE_PREFIXES: dict[str, str] = {
    "worktree ": "path",
    "HEAD ": "HEAD",
    "branch ": "branch",
}
_WORKTREE_FLAGS: dict[str, str] = {
    "bare": "bare",
    "detached": "detached",
}


def _apply_porcelain_line(current: dict[str, str], line: str) -> None:
    """Update *current* block dict from a single porcelain line."""
    for prefix, key in _WORKTREE_PREFIXES.items():
        if line.startswith(prefix):
            current[key] = line[len(prefix) :]
            return
    flag_key = _WORKTREE_FLAGS.get(line)
    if flag_key is not None:
        current[flag_key] = "true"


def _parse_worktree_porcelain(output: str) -> list[dict[str, str]]:
    """Parse ``git worktree list --porcelain`` into a list of dicts.

    Porcelain format emits blocks separated by blank lines, each block
    containing ``worktree``, ``HEAD``, and ``branch`` fields.
    """
    worktrees: list[dict[str, str]] = []
    current: dict[str, str] = {}

    for line in output.splitlines():
        if not line.strip():
            if current:
                worktrees.append(current)
                current = {}
            continue
        _apply_porcelain_line(current, line)

    if current:
        worktrees.append(current)

    return worktrees


class GitWorktreeTool(AXMTool):
    """Add, remove, or list git worktrees.

    Registered as ``git_worktree`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "git_worktree"

    def execute(  # type: ignore[override]
        self,
        *,
        action: str,
        path: str = ".",
        branch: str | None = None,
        base: str | None = None,
        force: bool = False,
        **kwargs: object,
    ) -> ToolResult:
        """Manage git worktrees.

        Args:
            action: One of ``add``, ``remove``, ``list``.
            path: For ``add``/``remove``: worktree path.
                  For ``list``: repository path.
            branch: Branch name for ``add`` action.
            base: Base ref for ``add`` (default: the repo's resolved
                  default branch).
            force: Force removal for ``remove`` action.

        Returns:
            ToolResult with worktree data on success.
        """
        resolved = Path(path).resolve()

        match action:
            case "list":
                return self._list(resolved)
            case "add":
                return self._add(
                    resolved,
                    branch=branch,
                    base=base or resolve_default_branch(resolved),
                )
            case "remove":
                return self._remove(resolved, force=force)
            case _:
                error = f"Invalid action {action!r}. Use 'add', 'remove', or 'list'."
                return ToolResult(
                    success=False,
                    error=error,
                    text=render_failure_text(error=error, data=None),
                )

    def _list(self, path: Path) -> ToolResult:
        """List all worktrees."""
        git_root = find_git_root(path)
        if git_root is None:
            return _not_a_repo_result(path)

        try:
            result = run_git(["worktree", "list", "--porcelain"], git_root)
        except subprocess.TimeoutExpired as exc:
            return timeout_error_result(exc)
        if result.returncode != 0:
            return _git_error_result(result)

        worktrees = _parse_worktree_porcelain(result.stdout)
        data: dict[str, object] = {"worktrees": worktrees}
        return ToolResult(success=True, data=data, text=render_list_text(data))

    def _add(
        self,
        path: Path,
        *,
        branch: str | None,
        base: str,
    ) -> ToolResult:
        """Add a new worktree."""
        git_root = find_git_root(path)
        if git_root is None:
            return _not_a_repo_result(path)

        cmd: list[str] = ["worktree", "add"]
        if branch:
            cmd.extend(["-b", branch])
        cmd.append(str(path))
        cmd.append(base)

        try:
            result = run_git(cmd, git_root)
        except subprocess.TimeoutExpired as exc:
            return timeout_error_result(exc)
        if result.returncode != 0:
            return _git_error_result(result)

        data: dict[str, object] = {
            "path": str(path),
            "branch": branch or base,
            "base": base,
        }
        return ToolResult(success=True, data=data, text=render_add_text(data))

    def _remove(self, path: Path, *, force: bool) -> ToolResult:
        """Remove an existing worktree."""
        git_root = find_git_root(path)
        if git_root is None:
            return _not_a_repo_result(path)

        cmd: list[str] = ["worktree", "remove", str(path)]
        if force:
            cmd.append("--force")

        try:
            result = run_git(cmd, git_root)
        except subprocess.TimeoutExpired as exc:
            return timeout_error_result(exc)
        if result.returncode != 0:
            return _git_error_result(result)

        data: dict[str, object] = {"removed": str(path)}
        return ToolResult(success=True, data=data, text=render_remove_text(data))
