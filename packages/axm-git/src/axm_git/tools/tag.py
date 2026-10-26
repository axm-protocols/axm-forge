"""GitTagTool — one-shot semver tag: preflight, compute, create, verify, push."""

from __future__ import annotations

import json
import logging
import re
import subprocess
import tomllib
from pathlib import Path
from typing import Literal

from axm.tools.base import AXMTool, ToolResult

from axm_git.core.runner import (
    gh_available,
    not_a_repo_error,
    resolve_default_branch,
    run_gh,
    run_git,
)
from axm_git.core.runner import (
    timeout_error_result as _timeout_error_result,
)
from axm_git.core.semver import compute_bump, parse_tag
from axm_git.core.tag_verification import (
    release_version,
    verify_remote_tag,
    verify_tag,
)
from axm_git.tools.tag_text import render_failure_text, render_text

__all__ = ["GitTagTool"]

logger = logging.getLogger(__name__)

type _PushOutcome = Literal["pushed", "rejected", "timed_out"]


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
                resolve_default_branch(path),
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
        current_bare = current_tag
        if current_bare and tag_prefix and current_bare.startswith(tag_prefix):
            current_bare = current_bare[len(tag_prefix) :]
        if current_bare and override_tuple <= parse_tag(current_bare):
            msg = (
                f"Version override {v!r} is not strictly greater than "
                f"the current tag {current_bare!r}"
            )
            raise ValueError(msg)
        return v, "override", False

    base = current_tag or "v0.0.0"
    if tag_prefix and base.startswith(tag_prefix):
        base = base[len(tag_prefix) :]
    bump_result = compute_bump(commits, base)
    return bump_result.next, bump_result.bump, bump_result.breaking


def _failure(error: str, data: dict[str, object] | None) -> ToolResult:
    """Build a dual-format failure ``ToolResult``."""
    return ToolResult(
        success=False,
        error=error,
        data=data if data is not None else {},
        text=render_failure_text(error=error, data=data),
    )


def _describe(exc: ValueError | subprocess.TimeoutExpired) -> str:
    """Render a verification exception as a one-line reason."""
    if isinstance(exc, subprocess.TimeoutExpired):
        return f"git timed out after {exc.timeout}s"
    return str(exc)


def _push_tag(path: Path, full_tag: str, object_id: str) -> tuple[_PushOutcome, str]:
    """Push the exact verified tag object to origin.

    Pushing ``<object>:refs/tags/<tag>`` (not the tag name) guarantees origin
    receives the object that was verified, even if the local ref is rewritten
    concurrently. A pre-existing remote tag is never overwritten (no force).

    Returns:
        ``(outcome, reason)`` — ``reason`` is empty when the push succeeded.
    """
    try:
        push = run_git(["push", "origin", f"{object_id}:refs/tags/{full_tag}"], path)
    except subprocess.TimeoutExpired as exc:
        return "timed_out", f"git push timed out after {exc.timeout}s"
    if push.returncode != 0:
        return "rejected", push.stderr.strip() or f"exit code {push.returncode}"
    return "pushed", ""


def _publish(
    path: Path,
    full_tag: str,
    tag_prefix: str,
    head_sha: str,
    data: dict[str, object],
) -> ToolResult:
    """Verify the freshly created local tag, push it, then verify origin.

    Every return carries *data* with ``pushed`` and ``remote_verified``.
    Failures never delete or overwrite the local or remote tag.
    """
    try:
        verified = verify_tag(path, full_tag, tag_prefix, head_sha)
    except (ValueError, subprocess.TimeoutExpired) as exc:
        return _failure(
            f"Tag {full_tag} created locally but failed verification "
            f"({_describe(exc)}); local tag kept, not pushed",
            data,
        )
    data.update(
        resolved_version=verified.version,
        tag_commit=verified.commit,
        tag_object=verified.object_id,
    )

    outcome, reason = _push_tag(path, full_tag, verified.object_id)
    if outcome == "rejected":
        # False-green guard: the Publish CI will never fire for this tag.
        return _failure(
            f"Tag {full_tag} created locally but push to origin failed: {reason}",
            data,
        )

    remote_error = verify_remote_tag(path, full_tag, verified)
    if outcome == "timed_out":
        # The push may or may not have landed: only origin's advertisement
        # can settle it, so an unconfirmed timeout stays ``pushed=False``.
        if remote_error:
            return _failure(
                f"Tag {full_tag} created locally but {reason} and origin "
                f"did not confirm it ({remote_error}); inspect origin before "
                "retrying",
                data,
            )
        logger.warning("%s, but origin advertises the verified tag", reason)
    data["pushed"] = True
    if remote_error:
        return _failure(remote_error, data)
    data["remote_verified"] = True
    return ToolResult(success=True, data=data, text=render_text(data))


class GitTagTool(AXMTool):
    """Create a semver release tag in one call.

    Performs preflight checks (clean tree, CI status), computes the
    next version from Conventional Commits, pins HEAD, creates an annotated
    tag, verifies its version and commit with Git reads, pushes the exact tag
    object and checks that origin advertises it. It never installs packages,
    runs ``uv`` or modifies the Python environment.

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
            ToolResult with tag, Git-verified version, commit, tag object,
            push status and remote verification status.
        """
        resolved = Path(path).resolve()
        tag_prefix = get_tag_prefix(resolved)

        try:
            # 1. Preflight: repo, clean tree, CI, commits
            result = _preflight(resolved, tag_prefix=tag_prefix)
            if isinstance(result, ToolResult):
                return result
            ci_check, current_tag, commits = result

            # 2. Compute and validate the version before any mutation.
            next_version, bump_type, breaking = resolve_version(
                version, current_tag, commits, tag_prefix=tag_prefix
            )
            full_tag = f"{tag_prefix}{next_version}"
            release_version(full_tag, tag_prefix)
            logger.info(
                "Tagging %s (bump=%s, breaking=%s)",
                full_tag,
                bump_type,
                breaking,
            )

            # 3. Pin the commit, then create the annotated tag on it.
            head_sha = _head_sha(resolved)
            if not head_sha:
                raise ValueError("Cannot resolve HEAD before tagging")
            tag_result = run_git(
                ["tag", "-a", full_tag, head_sha, "-m", full_tag], resolved
            )
        except ValueError as exc:
            return _failure(str(exc), None)
        except subprocess.TimeoutExpired as exc:
            return _timeout_error_result(exc)

        if tag_result.returncode != 0:
            return _failure(f"Failed to create tag: {tag_result.stderr.strip()}", None)

        data: dict[str, object] = {
            "tag": next_version,
            "full_tag": full_tag,
            "bump": bump_type,
            "breaking": breaking,
            "resolved_version": None,
            "version_source": "git_tag",
            "tag_commit": None,
            "tag_object": None,
            "pushed": False,
            "remote_verified": False,
            "ci_check": ci_check,
            "commits_included": len(commits),
            "current_tag": current_tag or "none",
        }
        # 4. Git evidence only: never rebuild, install or synchronize a venv.
        return _publish(resolved, full_tag, tag_prefix, head_sha, data)
