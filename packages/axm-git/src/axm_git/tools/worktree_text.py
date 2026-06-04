"""Text renderers for GitWorktreeTool dual-format ToolResult.

Transform the structured ``data`` dict produced by
:class:`axm_git.tools.worktree.GitWorktreeTool` into a compact text
representation, covering all three sub-modes::

    git_worktree | ✓ | list · {n} worktrees
    {path} {head7} {branch}
    ...

    git_worktree | ✓ | add · {branch} @ {base}
    {path}

    git_worktree | ✓ | remove
    {removed}

    git_worktree | ✗ | {error}
"""

from __future__ import annotations

__all__ = [
    "render_add_text",
    "render_failure_text",
    "render_list_text",
    "render_remove_text",
]

_SHORT_SHA = 7
_HEADS_PREFIX = "refs/heads/"


def _as_str(value: object, default: str = "") -> str:
    """Narrow *value* to ``str`` (heterogeneous ``dict[str, object]`` payload)."""
    return value if isinstance(value, str) else default


def _as_str_list(value: object) -> list[str]:
    """Narrow *value* to ``list[str]`` (heterogeneous payload)."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _worktree_line(entry: dict[str, object]) -> str:
    """Format one worktree block as ``{path} [{head7}] [{branch}|detached] [bare]``."""
    path = _as_str(entry.get("path"))
    parts = [path]
    head = _as_str(entry.get("HEAD"))
    if head:
        parts.append(head[:_SHORT_SHA])
    branch = _as_str(entry.get("branch"))
    if branch:
        short = (
            branch[len(_HEADS_PREFIX) :] if branch.startswith(_HEADS_PREFIX) else branch
        )
        parts.append(short)
    elif entry.get("detached"):
        parts.append("(detached)")
    if entry.get("bare"):
        parts.append("(bare)")
    return " ".join(parts)


def render_list_text(data: dict[str, object]) -> str:
    """Render the ``list`` sub-mode (``{"worktrees": [...]}``)."""
    raw = data.get("worktrees")
    worktrees = [w for w in raw if isinstance(w, dict)] if isinstance(raw, list) else []
    header = f"git_worktree | ✓ | list · {len(worktrees)} worktrees"
    if not worktrees:
        return header
    return "\n".join([header, *(_worktree_line(w) for w in worktrees)])


def render_add_text(data: dict[str, object]) -> str:
    """Render the ``add`` sub-mode (``{"path", "branch", "base"}``)."""
    branch = _as_str(data.get("branch"))
    base = _as_str(data.get("base"))
    path = _as_str(data.get("path"))
    return f"git_worktree | ✓ | add · {branch} @ {base}\n{path}"


def render_remove_text(data: dict[str, object]) -> str:
    """Render the ``remove`` sub-mode (``{"removed": ...}``)."""
    return f"git_worktree | ✓ | remove\n{_as_str(data.get('removed'))}"


def render_failure_text(*, error: str, data: dict[str, object] | None) -> str:
    """Render any failure (invalid action, not-a-repo, git error).

    Appends a child-repo hint when *data* carries ``suggestions``.
    """
    header = f"git_worktree | ✗ | {error}"
    suggestions = _as_str_list(data.get("suggestions")) if data else []
    if suggestions:
        return f"{header}\nhint: pass one as path: {', '.join(suggestions)}"
    return header
