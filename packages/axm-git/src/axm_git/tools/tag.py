"""GitTagTool — one-shot semver tag: preflight + compute + create + verify + push."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

from axm_git.core.runner import (
    detect_package_name,
    gh_available,
    not_a_repo_error,
    run_gh,
    run_git,
)
from axm_git.core.semver import compute_bump

__all__ = ["GitTagTool"]


def _check_ci(path: Path) -> str:
    """Check CI status via ``gh``.  Returns one of green/red/pending/skipped/error."""
    if not gh_available():
        return "skipped"
    try:
        ci = run_gh(
            [
                "run",
                "list",
                "--branch",
                "main",
                "--limit",
                "3",
                "--json",
                "status,conclusion,headSha",
            ],
            path,
        )
        if ci.returncode != 0 or not ci.stdout.strip():
            return "skipped"
        runs = json.loads(ci.stdout)
        if not runs:
            return "skipped"
        latest = runs[0]
        if latest.get("conclusion") == "success":
            return "green"
        if latest.get("status") == "in_progress":
            return "pending"
        return "red"
    except (json.JSONDecodeError, FileNotFoundError):
        return "error"


def _get_current_tag(path: Path) -> str | None:
    """Return the latest semver tag or ``None``."""
    result = run_git(["tag", "--sort=-v:refname"], path)
    tags = [t for t in result.stdout.strip().splitlines() if t.startswith("v")]
    return tags[0] if tags else None


def _get_commits_since(path: Path, tag: str | None) -> list[str]:
    """Return one-line commit summaries since *tag*."""
    log_range = f"{tag}..HEAD" if tag else "HEAD"
    log = run_git(["log", log_range, "--oneline"], path)
    return [line for line in log.stdout.strip().splitlines() if line.strip()]


def _verify_hatch_vcs(path: Path, pkg_name: str) -> str | None:
    """Rebuild package and read resolved version (best-effort)."""
    try:
        sync = subprocess.run(
            ["uv", "sync", "--reinstall-package", pkg_name],
            cwd=str(path),
            capture_output=True,
            text=True,
            check=False,
        )
        if sync.returncode != 0:
            return None
        ver = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-c",
                f"from importlib.metadata import version; print(version('{pkg_name}'))",
            ],
            cwd=str(path),
            capture_output=True,
            text=True,
            check=False,
        )
        if ver.returncode == 0:
            return ver.stdout.strip()
    except FileNotFoundError:
        pass
    return None


class GitTagTool(AXMTool):
    """Create a semver release tag in one call.

    Performs preflight checks (clean tree, CI status), computes the
    next version from Conventional Commits, creates an annotated tag,
    verifies hatch-vcs resolution, and pushes to origin.

    Registered as ``git_tag`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "git_tag"

    def execute(
        self,
        *,
        path: str = ".",
        version: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Create and push a semver tag.

        Args:
            path: Project root (required).
            version: Version override (optional, e.g. ``"v1.0.0"``).

        Returns:
            ToolResult with tag, version, and push status.
        """
        resolved = Path(path).resolve()
        version_override = version

        # 0. Fail fast with suggestions if not a git repo
        check = run_git(["rev-parse", "--git-dir"], resolved)
        if check.returncode != 0:
            return not_a_repo_error(check.stderr, resolved)

        # 1. Check clean tree
        status = run_git(["status", "--short"], resolved)
        if status.stdout.strip():
            return ToolResult(
                success=False,
                error="Uncommitted changes — commit first",
                data={"dirty_files": status.stdout.strip().splitlines()},
            )

        # 2. Check CI
        ci_check = _check_ci(resolved)
        if ci_check == "red":
            return ToolResult(
                success=False,
                error="CI is red — fix before tagging",
                data={"ci_check": ci_check},
            )

        # 3. Get current tag & commits
        current_tag = _get_current_tag(resolved)
        commits = _get_commits_since(resolved, current_tag)

        if not commits:
            return ToolResult(
                success=False,
                error="No commits since last tag",
                data={"current_tag": current_tag or "none"},
            )

        # 4. Compute version
        if version_override:
            next_version = version_override
            if not next_version.startswith("v"):
                next_version = f"v{next_version}"
            bump_type = "override"
            breaking = False
        else:
            base = current_tag or "v0.0.0"
            bump_result = compute_bump(commits, base)
            next_version = bump_result.next
            bump_type = bump_result.bump
            breaking = bump_result.breaking

        # 5. Create annotated tag
        tag_result = run_git(["tag", "-a", next_version, "-m", next_version], resolved)
        if tag_result.returncode != 0:
            return ToolResult(
                success=False,
                error=f"Failed to create tag: {tag_result.stderr.strip()}",
            )

        # 6. Verify hatch-vcs (best-effort)
        resolved_version = None
        pkg_name = detect_package_name(resolved)
        if pkg_name:
            resolved_version = _verify_hatch_vcs(resolved, pkg_name)

        # 7. Push tag
        push = run_git(["push", "origin", next_version], resolved)

        return ToolResult(
            success=True,
            data={
                "tag": next_version,
                "bump": bump_type,
                "breaking": breaking,
                "resolved_version": resolved_version,
                "pushed": push.returncode == 0,
                "ci_check": ci_check,
                "commits_included": len(commits),
                "current_tag": current_tag or "none",
            },
        )
