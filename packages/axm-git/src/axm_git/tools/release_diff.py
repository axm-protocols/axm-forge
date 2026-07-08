"""GitReleaseDiffTool — read-only SemVer bump decision for a package subdir."""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

from axm.tools.base import AXMTool, ToolResult

from axm_git.core.runner import find_git_root, not_a_repo_error, run_git
from axm_git.core.runner import timeout_error_result as _timeout_error_result
from axm_git.core.semver import classify_commit, compute_bump
from axm_git.tools.release_diff_text import render_failure_text, render_text
from axm_git.tools.tag import get_tag_prefix

__all__ = ["GitReleaseDiffTool"]

logger = logging.getLogger(__name__)

_FIRST_RELEASE_NEXT = "0.1.0"
_PUBLIC_API_RE = re.compile(r"(^|/)src/.+/__init__\.py$")


def _current_tag(path: Path, prefix: str) -> str | None:
    """Latest semver tag matching *prefix*, or ``None`` (read-only)."""
    result = run_git(["tag", "--sort=-v:refname"], path)
    full_prefix = f"{prefix}v"
    tags = [t for t in result.stdout.strip().splitlines() if t.startswith(full_prefix)]
    return tags[0] if tags else None


def _scoped_log(path: Path, tag: str | None, subdir: str) -> list[dict[str, object]]:
    """Parse ``git log <tag>..HEAD -- <subdir>`` into commit records."""
    log_range = f"{tag}..HEAD" if tag else "HEAD"
    result = run_git(["log", log_range, "--pretty=%h%x09%s", "--", subdir], path)
    commits: list[dict[str, object]] = []
    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        short_hash, _, subject = line.partition("\t")
        ctype, breaking = classify_commit(subject)
        commits.append(
            {
                "hash": short_hash,
                "type": ctype,
                "breaking": breaking,
                "subject": subject,
            }
        )
    return commits


def _aggregate_counts(commits: list[dict[str, object]]) -> dict[str, int]:
    """Tally one key per encountered commit type, plus a ``breaking`` count.

    Dynamic: every type actually present gets its own key, so no commit is
    dropped from the summary. Zero-valued entries are never emitted, and
    ``breaking`` only appears when at least one commit is breaking. Empty
    input yields an empty dict.
    """
    counts: dict[str, int] = {}
    for commit in commits:
        ctype = commit["type"]
        if isinstance(ctype, str):
            counts[ctype] = counts.get(ctype, 0) + 1
        if commit["breaking"]:
            counts["breaking"] = counts.get("breaking", 0) + 1
    return counts


def _diffstat(path: Path, tag: str | None, subdir: str) -> tuple[int, str]:
    """Return ``(files_changed, "+N / -M")`` from ``git diff --stat``."""
    diff_range = f"{tag}..HEAD" if tag else "HEAD"
    result = run_git(["diff", "--stat", diff_range, "--", subdir], path)
    summary = result.stdout.strip().splitlines()
    if not summary:
        return 0, "+0 / -0"
    last = summary[-1]
    files = _first_int(re.search(r"(\d+) files? changed", last))
    insertions = _first_int(re.search(r"(\d+) insertion", last))
    deletions = _first_int(re.search(r"(\d+) deletion", last))
    return files, f"+{insertions} / -{deletions}"


def _first_int(match: re.Match[str] | None) -> int:
    """Return the first capture group as ``int``, or 0 when *match* is None."""
    return int(match.group(1)) if match else 0


def _public_api_touched(path: Path, tag: str | None, subdir: str) -> bool:
    """True iff any changed path matches ``src/**/__init__.py``."""
    diff_range = f"{tag}..HEAD" if tag else "HEAD"
    result = run_git(["diff", "--name-only", diff_range, "--", subdir], path)
    return any(
        _PUBLIC_API_RE.search(line.strip())
        for line in result.stdout.strip().splitlines()
        if line.strip()
    )


def _suggest(
    commits: list[dict[str, object]], current_tag: str | None
) -> tuple[str, str, bool]:
    """Map commits onto ``(suggested_bump, suggested_next, breaking)``."""
    if current_tag is None:
        breaking = any(c["breaking"] for c in commits)
        has_feat = any(c["type"] == "feat" for c in commits)
        bump = "minor" if (has_feat or breaking) else "patch"
        return bump, _FIRST_RELEASE_NEXT, breaking
    base = current_tag[current_tag.rfind("/") + 1 :].lstrip("v")
    subjects = [str(c["subject"]) for c in commits]
    result = compute_bump(subjects, f"v{base}")
    return result.bump, result.next.lstrip("v"), result.breaking


class GitReleaseDiffTool(AXMTool):
    """Summarise commits/diff since the last tag to decide a SemVer bump.

    Strictly read-only: issues only ``log``, ``diff``, ``tag`` and
    ``rev-parse`` — never creates or pushes a tag. Scopes every ``log``
    and ``diff`` to the resolved package subdir so monorepo attribution
    is correct. Registered as ``git_release_diff`` via axm.tools.
    """

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "git_release_diff"

    def execute(self, *, path: str = ".", **kwargs: object) -> ToolResult:
        """Compute a read-only release diff for the package at *path*.

        Args:
            path: Package root (defaults to the current directory).

        Returns:
            ToolResult with current tag, commit summary, diffstat and a
            suggested next version.
        """
        resolved = Path(path).resolve()
        if find_git_root(resolved) is None:
            # False-green guard: without a repo, every read-only git call
            # returns empty, which would masquerade as a clean "first release
            # → 0.1.0". Surface the not-a-repo error instead.
            repo_err = not_a_repo_error("not a git repository", resolved)
            return ToolResult(
                success=repo_err.success,
                error=repo_err.error,
                data=repo_err.data,
                text=render_failure_text(
                    error=repo_err.error or "", data=repo_err.data
                ),
            )
        prefix = get_tag_prefix(resolved)
        try:
            data = self._collect(resolved, prefix)
        except subprocess.TimeoutExpired as exc:
            return _timeout_error_result(exc)
        return ToolResult(success=True, data=data, text=render_text(data))

    def _collect(self, resolved: Path, prefix: str) -> dict[str, object]:
        """Gather all read-only data for the success-path payload."""
        root = find_git_root(resolved)
        subdir = self._subdir(root, resolved)
        cwd = root or resolved
        current_tag = _current_tag(cwd, prefix)
        commits = _scoped_log(cwd, current_tag, subdir)
        files_changed, diffstat = _diffstat(cwd, current_tag, subdir)
        suggested_bump, suggested_next, breaking = _suggest(commits, current_tag)
        return {
            "current_tag": current_tag,
            "suggested_bump": suggested_bump,
            "suggested_next": suggested_next,
            "breaking": breaking,
            "commits_since": commits,
            "counts": _aggregate_counts(commits),
            "files_changed": files_changed,
            "diffstat": diffstat,
            "public_api_touched": _public_api_touched(cwd, current_tag, subdir),
        }

    @staticmethod
    def _subdir(root: Path | None, resolved: Path) -> str:
        """Package path relative to the git root (``.`` when at the root)."""
        if root is None:
            return "."
        try:
            rel = resolved.relative_to(root)
        except ValueError:
            return "."
        return str(rel)
