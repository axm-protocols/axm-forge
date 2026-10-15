"""Read-only workspace release planning through the shared AXMTool surface."""

from __future__ import annotations

import subprocess
from pathlib import Path

from axm.tools.base import AXMTool, ToolResult

from axm_git.core.release_plan import plan_releases
from axm_git.core.runner import find_git_root, timeout_error_result

__all__ = ["GitReleasePlanTool"]


class GitReleasePlanTool(AXMTool):
    """Plan package releases in mandatory dependency order without publishing."""

    @property
    def name(self) -> str:
        """Registered AXMTool name."""
        return "git_release_plan"

    def execute(
        self, *, path: str = ".", ref: str = "HEAD", **kwargs: object
    ) -> ToolResult:
        """Return the pinned workspace plan; never fetch, checkout, tag or push.

        Args:
            path: Repository or package directory inside the repository.
            ref: Commit or ref to plan, resolved once before reading metadata.

        Returns:
            Structured ordered package/version plan, or an explicit blocker.
        """
        root = find_git_root(Path(path).resolve())
        if root is None:
            return ToolResult(success=False, error="Not a Git repository")
        try:
            data = plan_releases(root, ref)
        except subprocess.TimeoutExpired as exc:
            return timeout_error_result(exc)
        except (ValueError, OSError) as exc:
            return ToolResult(success=False, error=str(exc))
        packages = data["packages"]
        assert isinstance(packages, list)
        lines = [f"git_release_plan | {data['ref']} | {len(packages)} packages"]
        for entry in packages:
            assert isinstance(entry, dict)
            lines.append(
                f"{entry['name']} {entry['suggested_next']} | {entry['action']}"
            )
        return ToolResult(success=True, data=data, text="\n".join(lines))
