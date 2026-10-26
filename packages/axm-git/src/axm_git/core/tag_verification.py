"""Read-only verification of release tags and their remote publication.

Every check here reads Git objects or remote refs only: no package manager,
build backend or installed distribution is consulted, so verifying a release
tag never mutates the Python environment.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from axm_git.core.runner import run_git
from axm_git.core.semver import parse_tag

__all__ = ["VerifiedTag", "release_version", "verify_remote_tag", "verify_tag"]

# ``git ls-remote --exit-code`` returns 2 when no ref matches the patterns.
_LS_REMOTE_NO_MATCH = 2


@dataclass(frozen=True)
class VerifiedTag:
    """Git evidence, independent of installed package or build metadata.

    Attributes:
        version: Bare SemVer read from the tag name (``"1.2.3"``).
        commit: Commit SHA the tag peels to.
        object_id: SHA of the annotated tag object itself.
    """

    version: str
    commit: str
    object_id: str


def release_version(full_tag: str, prefix: str) -> str:
    """Return the bare SemVer encoded in *full_tag* (``{prefix}vX.Y.Z``).

    Pure validation, no Git access: the tag must start with the package
    prefix followed by ``v`` and a strict ``MAJOR.MINOR.PATCH`` version.

    Raises:
        ValueError: If the prefix does not match or the version is not SemVer.
    """
    expected = f"{prefix}v"
    if not full_tag.startswith(expected):
        msg = f"Tag {full_tag!r} does not match package prefix {expected!r}"
        raise ValueError(msg)
    return ".".join(str(part) for part in parse_tag(full_tag[len(prefix) :]))


def _revision(path: Path, ref: str) -> str:
    """Read an exact Git object without changing the working tree."""
    result = run_git(["rev-parse", "--verify", ref], path)
    if result.returncode != 0 or not result.stdout.strip():
        msg = f"Cannot resolve {ref}: {result.stderr.strip()}"
        raise ValueError(msg)
    return result.stdout.strip()


def verify_tag(
    path: Path, full_tag: str, prefix: str, expected_commit: str
) -> VerifiedTag:
    """Validate the tag version and its pinned commit using Git reads only.

    This does not resolve hatch-vcs build configuration or inspect an installed
    distribution. Artifact version validation belongs to the publication CI.

    Raises:
        ValueError: If the version is invalid, the tag cannot be resolved, or
            it does not peel to *expected_commit*.
        subprocess.TimeoutExpired: If a Git read exceeds its timeout.
    """
    version = release_version(full_tag, prefix)
    ref = f"refs/tags/{full_tag}"
    object_id = _revision(path, ref)
    commit = _revision(path, f"{object_id}^{{commit}}")
    if commit != expected_commit:
        msg = f"Tag {full_tag} targets {commit}, expected {expected_commit}"
        raise ValueError(msg)
    return VerifiedTag(version, commit, object_id)


def _advertised_refs(stdout: str) -> dict[str, str]:
    """Parse ``git ls-remote`` output into ``{refname: object_id}``."""
    refs: dict[str, str] = {}
    for line in stdout.splitlines():
        object_id, separator, name = line.partition("\t")
        if separator:
            refs[name.strip()] = object_id.strip()
    return refs


def _remote_mismatch(
    refs: dict[str, str], full_tag: str, tag: VerifiedTag
) -> str | None:
    """Describe how the advertised refs differ from *tag*, or ``None``."""
    ref = f"refs/tags/{full_tag}"
    advertised = refs.get(ref)
    if advertised is None:
        return f"origin does not advertise {ref}"
    peeled = refs.get(f"{ref}^{{}}")
    if peeled is None:
        return (
            f"origin advertises {ref} as a lightweight tag on {advertised}, "
            f"expected annotated tag object {tag.object_id}"
        )
    if advertised != tag.object_id:
        return f"origin tag object is {advertised}, expected {tag.object_id}"
    if peeled != tag.commit:
        return f"origin tag peels to {peeled}, expected {tag.commit}"
    return None


def verify_remote_tag(path: Path, full_tag: str, tag: VerifiedTag) -> str | None:
    """Return an error unless origin advertises the same tag object and commit.

    Reads ``git ls-remote`` only. An annotated tag is advertised twice: the
    tag object under ``refs/tags/<tag>`` and its peeled commit under
    ``refs/tags/<tag>^{}``. A lightweight tag (no peeled line), a different
    tag object or a different commit are all reported as mismatches.
    """
    ref = f"refs/tags/{full_tag}"
    try:
        result = run_git(
            ["ls-remote", "--exit-code", "--tags", "origin", ref, f"{ref}^{{}}"],
            path,
        )
    except subprocess.TimeoutExpired as exc:
        return (
            f"Remote verification of {full_tag} timed out after {exc.timeout}s; "
            "inspect origin before retrying"
        )
    if result.returncode not in (0, _LS_REMOTE_NO_MATCH):
        return f"Cannot verify remote tag {full_tag}: {result.stderr.strip()}"
    mismatch = _remote_mismatch(_advertised_refs(result.stdout), full_tag, tag)
    if mismatch:
        return (
            f"Remote tag {full_tag} does not match the verified local tag: {mismatch}"
        )
    return None
