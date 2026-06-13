"""Shared recovery for an already-existing GitHub pull request.

When ``gh pr create`` fails because a PR already exists for the branch,
both :class:`~axm_git.tools.pr.GitPRTool` and
:class:`~axm_git.hooks.create_pr.CreatePRHook` recover the existing PR via
``gh pr view``. This module factors that recovery into a single helper that
returns a result-agnostic structure; each caller adapts it to its own
result type (``ToolResult`` / ``HookResult``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from axm_git.core.runner import run_gh

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["PRRecovery", "is_already_exists", "recover_existing_pr"]


@dataclass(frozen=True)
class PRRecovery:
    """Normalized result of recovering an existing pull request.

    On success ``error`` is ``None`` and ``url``/``number`` are populated.
    On failure ``error`` carries the reason and ``url``/``number`` are empty.
    """

    url: str = ""
    number: str = ""
    already_existed: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        """Whether recovery succeeded."""
        return self.error is None


def is_already_exists(stderr: str) -> bool:
    """Return ``True`` when *stderr* signals an existing PR (case-insensitive)."""
    return "already exists" in stderr.lower()


def recover_existing_pr(working_dir: Path) -> PRRecovery:
    """Resolve the existing PR via ``gh pr view`` after an 'already exists' error.

    Args:
        working_dir: Repository working directory.

    Returns:
        A :class:`PRRecovery` with ``url``/``number``/``already_existed`` on
        success, or with ``error`` set when the PR could not be retrieved.
    """
    view = run_gh(["pr", "view", "--json", "url,number"], working_dir)
    if view.returncode != 0:
        return PRRecovery(
            error=f"PR already exists but could not retrieve it: {view.stderr}"
        )
    try:
        data = json.loads(view.stdout)
        return PRRecovery(
            url=data["url"],
            number=str(data["number"]),
            already_existed=True,
        )
    except (json.JSONDecodeError, KeyError) as exc:
        return PRRecovery(error=f"PR already exists but could not parse it: {exc}")
