"""Semantic versioning — parse commits and compute next version."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["VersionBump", "compute_bump", "parse_tag"]

_TAG_RE = re.compile(r"v?(\d+)\.(\d+)\.(\d+)")
_BREAKING_RE = re.compile(r"^[a-z]+(\(.+\))?!:")
_FEAT_RE = re.compile(r"^feat(\(.+\))?:")


@dataclass(frozen=True)
class VersionBump:
    """Result of a semver computation.

    Attributes:
        current: Current tag (e.g. ``"v0.7.0"``).
        next: Next tag (e.g. ``"v0.8.0"``).
        bump: Bump type (``"major"``, ``"minor"``, or ``"patch"``).
        commits: One-line commit summaries since last tag.
        breaking: Whether a breaking change was detected.
    """

    current: str
    next: str
    bump: str
    commits: list[str]
    breaking: bool


def parse_tag(tag: str) -> tuple[int, int, int]:
    """Parse a semver tag string into ``(major, minor, patch)``.

    Args:
        tag: Version string, with or without ``v`` prefix.

    Returns:
        Tuple of (major, minor, patch).

    Raises:
        ValueError: If the tag doesn't match semver format.
    """
    m = _TAG_RE.match(tag)
    if not m:
        msg = f"Invalid semver tag: {tag!r}"
        raise ValueError(msg)
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def _classify_commits(
    commits: list[str],
) -> tuple[bool, bool]:
    """Scan commits for breaking changes and features.

    Returns:
        ``(has_breaking, has_feat)``.
    """
    has_breaking = False
    has_feat = False
    for commit in commits:
        msg = commit.split(" ", 1)[1] if " " in commit else commit
        if _BREAKING_RE.match(msg) or "BREAKING CHANGE:" in msg:
            has_breaking = True
        elif _FEAT_RE.match(msg):
            has_feat = True
    return has_breaking, has_feat


def _next_version(
    major: int, minor: int, patch: int, *, has_breaking: bool, has_feat: bool
) -> tuple[str, str]:
    """Compute bump type and next version string.

    Returns:
        ``(bump, next_version)``.
    """
    if has_breaking:
        bump = "major" if major > 0 else "minor"
    elif has_feat:
        bump = "minor"
    else:
        bump = "patch"

    match bump:
        case "major":
            return bump, f"v{major + 1}.0.0"
        case "minor":
            return bump, f"v{major}.{minor + 1}.0"
        case _:
            return bump, f"v{major}.{minor}.{patch + 1}"


def compute_bump(commits: list[str], current_tag: str) -> VersionBump:
    """Compute the next semver version from commit messages.

    Rules (pre-1.0, i.e. major == 0):
        - ``feat!:`` or ``BREAKING CHANGE:`` → **minor** bump
        - ``feat:`` → **minor** bump
        - everything else → **patch** bump

    Rules (post-1.0):
        - ``feat!:`` or ``BREAKING CHANGE:`` → **major** bump
        - ``feat:`` → **minor** bump
        - everything else → **patch** bump

    Args:
        commits: One-line commit messages (e.g. from ``git log --oneline``).
        current_tag: Current version tag (e.g. ``"v0.7.0"``).

    Returns:
        VersionBump with computed next version.
    """
    logger.info("Computing version bump from %s", current_tag)
    major, minor, patch = parse_tag(current_tag)
    has_breaking, has_feat = _classify_commits(commits)
    bump, next_version = _next_version(
        major, minor, patch, has_breaking=has_breaking, has_feat=has_feat
    )

    return VersionBump(
        current=current_tag,
        next=next_version,
        bump=bump,
        commits=commits,
        breaking=has_breaking,
    )
