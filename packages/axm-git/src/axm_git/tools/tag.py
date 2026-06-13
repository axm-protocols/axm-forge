"""GitTagTool — one-shot semver tag: preflight + compute + create + verify + push."""

from __future__ import annotations

import json
import logging
import re
import subprocess
import tomllib
from pathlib import Path

from axm.tools.base import AXMTool, ToolResult

from axm_git.core.runner import (
    detect_package_name,
    gh_available,
    not_a_repo_error,
    run_gh,
    run_git,
)
from axm_git.core.runner import (
    timeout_error_result as _timeout_error_result,
)
from axm_git.core.semver import compute_bump, parse_tag
from axm_git.tools.tag_text import render_failure_text, render_text

__all__ = ["GitTagTool"]

logger = logging.getLogger(__name__)


def _head_sha(path: Path) -> str | None:
    """Resolve the current HEAD SHA via ``git rev-parse``, or None on failure."""
    rev = run_git(["rev-parse", "HEAD"], path)
    if rev.returncode != 0:
        return None
    sha = rev.stdout.strip()
    return sha or None


def _sha_matches(run_sha: str, head_sha: str) -> bool:
    """Compare a CI run's headSha with HEAD, tolerating short vs full SHAs.

    ``gh`` may return either a short or a full SHA; we prefix-match on the
    longer of the two so an abbreviated SHA still correlates with HEAD.
    """
    if not run_sha:
        return False
    longer, shorter = (
        (run_sha, head_sha) if len(run_sha) >= len(head_sha) else (head_sha, run_sha)
    )
    return longer.startswith(shorter)


def _verdict(run: dict[str, object]) -> str:
    """Map a single CI run to the green/pending/red vocabulary."""
    if run.get("conclusion") == "success":
        return "green"
    if run.get("status") == "in_progress":
        return "pending"
    return "red"


def check_ci(path: Path) -> str:
    """Check CI status via ``gh`` for the CI run matching HEAD.

    Returns one of green/red/pending/skipped/error. The status is derived
    from the run whose ``headSha`` matches the current HEAD SHA, never from
    ``runs[0]`` unconditionally: a stale green (HEAD moved past it) or a red
    on an unrelated commit must not influence the verdict. When no run
    matches HEAD, returns ``pending`` (block tagging until CI exists for the
    exact commit being tagged).
    """
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
        head_sha = _head_sha(path)
        if head_sha is None:
            return "pending"
        for run in runs:
            if _sha_matches(str(run.get("headSha") or ""), head_sha):
                return _verdict(run)
        return "pending"
    except (json.JSONDecodeError, FileNotFoundError):
        return "error"


def get_tag_prefix(path: Path) -> str:
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


def verify_hatch_vcs(path: Path, pkg_name: str) -> str | None:
    """Rebuild package and read resolved version (best-effort)."""
    try:
        sync = subprocess.run(
            ["uv", "sync", "--reinstall-package", pkg_name],
            cwd=str(path),
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
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
            timeout=60,
        )
        if ver.returncode == 0:
            return ver.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
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
        repo_err = not_a_repo_error(check.stderr, path)
        return ToolResult(
            success=repo_err.success,
            error=repo_err.error,
            data=repo_err.data,
            text=render_failure_text(error=repo_err.error or "", data=repo_err.data),
        )

    status = run_git(["status", "--short"], path)
    if status.stdout.strip():
        error = "Uncommitted changes — commit first"
        data: dict[str, object] = {"dirty_files": status.stdout.strip().splitlines()}
        return ToolResult(
            success=False,
            error=error,
            data=data,
            text=render_failure_text(error=error, data=data),
        )

    ci_check = check_ci(path)
    if ci_check == "red":
        error = "CI is red — fix before tagging"
        data = {"ci_check": ci_check}
        return ToolResult(
            success=False,
            error=error,
            data=data,
            text=render_failure_text(error=error, data=data),
        )

    current_tag = _get_current_tag(path, prefix=tag_prefix)
    commits = _get_commits_since(path, current_tag)

    if not commits:
        error = "No commits since last tag"
        data = {"current_tag": current_tag or "none"}
        return ToolResult(
            success=False,
            error=error,
            data=data,
            text=render_failure_text(error=error, data=data),
        )

    return ci_check, current_tag, commits


def resolve_version(
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
        override_tuple = parse_tag(v)
        if current_tag and override_tuple <= parse_tag(current_tag):
            msg = (
                f"Version override {v!r} is not strictly greater than "
                f"the current tag {current_tag!r}"
            )
            raise ValueError(msg)
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
        **kwargs: object,
    ) -> ToolResult:
        """Create and push a semver tag.

        Args:
            path: Project root (required).
            version: Version override (optional, e.g. ``"v1.0.0"``).

        Returns:
            ToolResult with tag, version, and push status.
        """
        resolved = Path(path).resolve()
        tag_prefix = get_tag_prefix(resolved)

        try:
            # 1. Preflight: repo, clean tree, CI, commits
            result = _preflight(resolved, tag_prefix=tag_prefix)
            if isinstance(result, ToolResult):
                return result
            ci_check, current_tag, commits = result

            # 2. Compute version
            next_version, bump_type, breaking = resolve_version(
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
                error = f"Failed to create tag: {tag_result.stderr.strip()}"
                return ToolResult(
                    success=False,
                    error=error,
                    text=render_failure_text(error=error, data=None),
                )

            # 4. Verify hatch-vcs (best-effort)
            resolved_version = None
            pkg_name = detect_package_name(resolved)
            if pkg_name:
                resolved_version = verify_hatch_vcs(resolved, pkg_name)

            # 5. Push tag
            push = run_git(["push", "origin", full_tag], resolved)
        except ValueError as exc:
            error = str(exc)
            return ToolResult(
                success=False,
                error=error,
                text=render_failure_text(error=error, data=None),
            )
        except subprocess.TimeoutExpired as exc:
            return _timeout_error_result(exc)

        data: dict[str, object] = {
            "tag": next_version,
            "full_tag": full_tag,
            "bump": bump_type,
            "breaking": breaking,
            "resolved_version": resolved_version,
            "pushed": push.returncode == 0,
            "ci_check": ci_check,
            "commits_included": len(commits),
            "current_tag": current_tag or "none",
        }
        return ToolResult(success=True, data=data, text=render_text(data))
