"""GitWorktreeTool — add, remove, and list git worktrees."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

from axm_git.core.runner import find_git_root, not_a_repo_error, run_git

__all__ = ["GitWorktreeTool"]


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

    def execute(  # type: ignore[override]  # Tool accepts specific args instead of generic kwargs
        self,
        *,
        action: str,
        path: str = ".",
        branch: str | None = None,
        base: str = "main",
        force: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        """Manage git worktrees.

        Args:
            action: One of ``add``, ``remove``, ``list``.
            path: For ``add``/``remove``: worktree path.
                  For ``list``: repository path.
            branch: Branch name for ``add`` action.
            base: Base ref for ``add`` (default ``main``).
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
                    base=base,
                )
            case "remove":
                return self._remove(resolved, force=force)
            case _:
                return ToolResult(
                    success=False,
                    error=(
                        f"Invalid action {action!r}. Use 'add', 'remove', or 'list'."
                    ),
                )

    def _list(self, path: Path) -> ToolResult:
        """List all worktrees."""
        git_root = find_git_root(path)
        if git_root is None:
            return not_a_repo_error("not a git repository", path)

        result = run_git(["worktree", "list", "--porcelain"], git_root)
        if result.returncode != 0:
            return ToolResult(
                success=False,
                error=result.stderr.strip() or result.stdout.strip(),
            )

        worktrees = _parse_worktree_porcelain(result.stdout)
        return ToolResult(
            success=True,
            data={"worktrees": worktrees},
        )

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
            return not_a_repo_error("not a git repository", path)

        cmd: list[str] = ["worktree", "add"]
        if branch:
            cmd.extend(["-b", branch])
        cmd.append(str(path))
        cmd.append(base)

        result = run_git(cmd, git_root)
        if result.returncode != 0:
            return ToolResult(
                success=False,
                error=result.stderr.strip() or result.stdout.strip(),
            )

        return ToolResult(
            success=True,
            data={
                "path": str(path),
                "branch": branch or base,
                "base": base,
            },
        )

    def _remove(self, path: Path, *, force: bool) -> ToolResult:
        """Remove an existing worktree."""
        git_root = find_git_root(path)
        if git_root is None:
            return not_a_repo_error("not a git repository", path)

        cmd: list[str] = ["worktree", "remove", str(path)]
        if force:
            cmd.append("--force")

        result = run_git(cmd, git_root)
        if result.returncode != 0:
            return ToolResult(
                success=False,
                error=result.stderr.strip() or result.stdout.strip(),
            )

        return ToolResult(
            success=True,
            data={"removed": str(path)},
        )
