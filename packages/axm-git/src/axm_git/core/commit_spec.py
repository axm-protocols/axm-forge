"""Shared commit spec validation and Git hook autofix-retry plumbing."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Protocol, cast

from axm_git.core.runner import run_git, stage_spec_files

__all__ = [
    "AutofixRetry",
    "attempt_commit_with_autofix_retry",
    "validate_commit_spec",
]

logger = logging.getLogger(__name__)

#: Marker emitted by git when a commit hook auto-fixed staged files.
AUTOFIX_MARKER = "files were modified"

_REQUIRED_SPEC_KEYS = {"message", "files"}


class _GitResultLike(Protocol):
    """Minimal protocol matching ``subprocess.CompletedProcess`` and the
    ``SimpleNamespace`` fallback returned on a re-stage failure.
    """

    returncode: int
    stdout: str
    stderr: str


def validate_commit_spec(
    spec: dict[str, object] | None,
) -> tuple[dict[str, object] | None, str | None]:
    """Validate a ``commit_spec`` dict (pure; stricter merged contract).

    Requires a non-empty ``message`` AND a non-empty ``files`` list — the
    stricter of the two prior per-surface validators.  Returns
    ``(spec, error_message)`` where *spec* is ``None`` when an error is set;
    each surface wraps the error string in its own result type.
    """
    if not spec:
        return None, "from_outputs=True but no commit_spec in context"
    if not isinstance(spec, dict):
        return None, "commit_spec must be a dict"
    missing = _REQUIRED_SPEC_KEYS - set(spec)
    if missing:
        return None, (
            f"commit_spec missing {', '.join(repr(k) for k in sorted(missing))}"
        )
    if not spec.get("files"):
        return None, "empty files list"
    if not spec.get("message"):
        return None, "empty message"
    return spec, None


@dataclass
class AutofixRetry:
    """Outcome of an autofix-aware commit retry.

    Attributes:
        result: The final GitResult-like object (returncode/stdout/stderr).
        retried: Whether a re-stage + retry was actually performed.
        auto_fixed: Files the commit hook modified, captured *before*
            re-staging (the subsequent ``git add`` would empty the diff).
            Empty when no auto-fix occurred.
    """

    result: _GitResultLike
    retried: bool
    auto_fixed: list[str]


def _head_sha(git_root: Path) -> str:
    """Return the current HEAD commit sha, or ``""`` when HEAD is unborn."""
    head = run_git(["rev-parse", "HEAD"], git_root)
    return head.stdout.strip() if head.returncode == 0 else ""


def _reconcile_with_repo_state(
    result: _GitResultLike,
    git_root: Path,
    head_before: str,
) -> _GitResultLike:
    """Trust the repository state over a non-zero commit exit code.

    A commit hook can land a commit — it auto-committed, or the runner exits
    non-zero after a successful re-stage + retry — while ``git commit`` still
    returns a non-zero code (the AXM-22 false red: commit created, tree clean,
    yet the tool would report failure). When HEAD advanced past *head_before*
    the commit is real, so return a success-shaped result carrying the original
    output. Otherwise return *result* unchanged so genuine failures (hook
    reject, git error/conflict, nothing-to-commit) keep their non-zero code.
    """
    if result.returncode == 0:
        return result
    head_after = _head_sha(git_root)
    if head_after and head_after != head_before:
        return cast(
            "_GitResultLike",
            SimpleNamespace(returncode=0, stdout=result.stdout, stderr=result.stderr),
        )
    return result


def attempt_commit_with_autofix_retry(
    cmd: list[str],
    files: list[str],
    git_root: Path,
    first_result: _GitResultLike,
    *,
    working_dir: Path | None = None,
) -> AutofixRetry:
    """Re-stage + retry *cmd* once when a commit hook auto-fixed files.

    Detection is on the combined stdout+stderr of *first_result*: when the
    canonical ``"files were modified"`` marker is present, the modified
    files are captured (``git diff --name-only`` *before* re-staging), the
    spec *files* are re-staged via the subdir-aware resolver, and *cmd* is
    retried once.  Otherwise *first_result* is returned unchanged.
    """
    if first_result.returncode == 0:
        return AutofixRetry(result=first_result, retried=False, auto_fixed=[])

    output = first_result.stdout + first_result.stderr
    if AUTOFIX_MARKER not in output:
        return AutofixRetry(result=first_result, retried=False, auto_fixed=[])

    logger.warning("Commit hook auto-fixed files, re-staging and retrying")
    diff = run_git(["diff", "--name-only"], git_root)
    auto_fixed = [f for f in diff.stdout.strip().splitlines() if f.strip()]

    restage_err = stage_spec_files(files, git_root, working_dir=working_dir)
    if restage_err:
        failed = cast(
            "_GitResultLike",
            SimpleNamespace(returncode=1, stdout="", stderr=restage_err),
        )
        return AutofixRetry(result=failed, retried=True, auto_fixed=auto_fixed)

    head_before = _head_sha(git_root)
    retried = run_git(cmd, git_root)
    reconciled = _reconcile_with_repo_state(retried, git_root, head_before)
    return AutofixRetry(result=reconciled, retried=True, auto_fixed=auto_fixed)
