"""Shared commit plumbing: spec validation, autofix-retry, result building.

Single source of truth for the commit helpers used by both surfaces
(:class:`axm_git.tools.commit.GitCommitTool` and
:class:`axm_git.hooks.commit_phase.CommitPhaseHook`).  The validation is
pure (returns ``(spec, err)``) so each surface wraps the error string in
its own result type; the autofix-retry and HookResult builder are shared
verbatim.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Protocol, cast

from axm.hooks.base import HookResult

from axm_git.core.identity import GitIdentity
from axm_git.core.runner import run_git, stage_spec_files

__all__ = [
    "AutofixRetry",
    "attempt_commit_with_autofix_retry",
    "build_commit_result",
    "retry_commit_on_autofix",
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

    retried = run_git(cmd, git_root)
    return AutofixRetry(result=retried, retried=True, auto_fixed=auto_fixed)


def retry_commit_on_autofix(
    files: list[str],
    cmd: list[str],
    git_root: Path,
    first_result: _GitResultLike,
    *,
    working_dir: Path | None = None,
) -> _GitResultLike:
    """Hook-facing wrapper: return only the retried GitResult.

    Thin adapter over :func:`attempt_commit_with_autofix_retry` for callers
    that only need the final result object (the commit-phase hook).
    """
    return attempt_commit_with_autofix_retry(
        cmd, files, git_root, first_result, working_dir=working_dir
    ).result


def build_commit_result(
    git_root: Path,
    message: str,
    identity: GitIdentity | None,
    warnings: list[str],
) -> HookResult:
    """Build a successful commit :class:`HookResult`.

    Reads the current HEAD short hash and assembles the result dict
    with optional identity and warning fields.
    """
    hash_result = run_git(["rev-parse", "--short", "HEAD"], git_root)
    result_kw: dict[str, Any] = {  # type: ignore[explicit-any]  # heterogeneous metadata payload for HookResult.ok(**metadata: Any)
        "commit": hash_result.stdout.strip(),
        "message": message,
    }
    if identity:
        result_kw["author_name"] = identity.name
        result_kw["author_email"] = identity.email
    if warnings:
        result_kw["warnings"] = warnings
    return HookResult.ok(**result_kw)
