"""GitTagTool — one-shot semver tag: preflight + compute + create + verify + push."""

from __future__ import annotations

import json
import logging
import re
import subprocess
import tomllib
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

logger = logging.getLogger(__name__)


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


def _get_tag_prefix(path: Path) -> str:
    """Read tag prefix from pyproject.toml ``tag-pattern`` (e.g. ``git/``).

    Returns the prefix string (e.g. ``"git/"``) or ``""`` if none.
    """
    pyproject = path / "pyproject.toml"
    if not pyproject.exists():
        return ""
    try:
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        pattern = (
            data.get("tool", {})
            .get("hatch", {})
            .get("version", {})
            .get("tag-pattern", "")
        )
        # Extract prefix before "v" from patterns like "git/v(?P<version>.*)"
        m = re.match(r"^(.+?)v\(", pattern)
        return m.group(1) if m else ""
    except (OSError, tomllib.TOMLDecodeError):
        return ""


def _get_current_tag(path: Path, prefix: str = "") -> str | None:
    """Return the latest semver tag or ``None``.

    Args:
        path: Repository root.
        prefix: Tag prefix (e.g. ``"git/"``).  If empty, matches plain ``v*`` tags.
    """
    result = run_git(["tag", "--sort=-v:refname"], path)
    full_prefix = f"{prefix}v"
    tags = [t for t in result.stdout.strip().splitlines() if t.startswith(full_prefix)]
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


def _preflight(
    path: Path, *, tag_prefix: str = ""
) -> ToolResult | tuple[str, str | None, list[str]]:
    """Run preflight checks: repo, clean tree, CI, tag, commits.

    Returns:
        ``ToolResult`` on failure, or ``(ci_check, current_tag, commits)`` on success.
    """
    check = run_git(["rev-parse", "--git-dir"], path)
    if check.returncode != 0:
        return not_a_repo_error(check.stderr, path)

    status = run_git(["status", "--short"], path)
    if status.stdout.strip():
        return ToolResult(
            success=False,
            error="Uncommitted changes — commit first",
            data={"dirty_files": status.stdout.strip().splitlines()},
        )

    ci_check = _check_ci(path)
    if ci_check == "red":
        return ToolResult(
            success=False,
            error="CI is red — fix before tagging",
            data={"ci_check": ci_check},
        )

    current_tag = _get_current_tag(path, prefix=tag_prefix)
    commits = _get_commits_since(path, current_tag)

    if not commits:
        return ToolResult(
            success=False,
            error="No commits since last tag",
            data={"current_tag": current_tag or "none"},
        )

    return ci_check, current_tag, commits


def _resolve_version(
    version_override: str | None,
    current_tag: str | None,
    commits: list[str],
    *,
    tag_prefix: str = "",
) -> tuple[str, str, bool]:
    """Resolve the next version tag.

    Returns:
        ``(next_version, bump_type, breaking)``.
    """
    if version_override:
        v = (
            version_override
            if version_override.startswith("v")
            else f"v{version_override}"
        )
        return v, "override", False

    base = current_tag or "v0.0.0"
    if tag_prefix and base.startswith(tag_prefix):
        base = base[len(tag_prefix) :]
    bump_result = compute_bump(commits, base)
    return bump_result.next, bump_result.bump, bump_result.breaking


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
        tag_prefix = _get_tag_prefix(resolved)

        # 1. Preflight: repo, clean tree, CI, commits
        result = _preflight(resolved, tag_prefix=tag_prefix)
        if isinstance(result, ToolResult):
            return result
        ci_check, current_tag, commits = result

        # 2. Compute version
        next_version, bump_type, breaking = _resolve_version(
            version, current_tag, commits, tag_prefix=tag_prefix
        )
        logger.info(
            "Tagging %s (bump=%s, breaking=%s)",
            next_version,
            bump_type,
            breaking,
        )

        # 3. Create annotated tag
        full_tag = f"{tag_prefix}{next_version}"
        tag_result = run_git(["tag", "-a", full_tag, "-m", full_tag], resolved)
        if tag_result.returncode != 0:
            return ToolResult(
                success=False,
                error=f"Failed to create tag: {tag_result.stderr.strip()}",
            )

        # 4. Verify hatch-vcs (best-effort)
        resolved_version = None
        pkg_name = detect_package_name(resolved)
        if pkg_name:
            resolved_version = _verify_hatch_vcs(resolved, pkg_name)

        # 5. Push tag
        push = run_git(["push", "origin", full_tag], resolved)

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
