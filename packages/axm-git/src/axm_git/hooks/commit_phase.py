"""Commit-phase hook action.

Stages all changes and commits with ``[axm] {phase_name}``.
Supports a ``from_outputs`` mode that reads ``commit_spec``
from context for targeted file staging.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from axm.hooks.base import HookResult

from axm_git.core.commit_spec import (
    _GitResultLike,
    build_commit_result,
    retry_commit_on_autofix,
    validate_commit_spec,
)
from axm_git.core.identity import (  # noqa: F401 (author_args: mock target)
    author_args,
    resolve_identity,
)
from axm_git.core.runner import (
    _resolve_repo_path,
    find_git_root,
    run_git,
    stage_spec_files,
)

logger = logging.getLogger(__name__)

__all__ = ["CommitPhaseHook"]


def build_commit_cmd(
    message: str,
    body: str | None,
    *,
    skip_hooks: bool = True,
    author: str | None = None,
) -> list[str]:
    """Build the ``git commit`` argument list.

    Args:
        message: Commit summary line.
        body: Optional extended commit body.
        skip_hooks: Append ``--no-verify`` when *True*.
        author: Git ``--author`` value (``"Name <email>"``).
            When *None*, git uses the default identity.
    """
    cmd = ["commit", "-m", message]
    if body:
        cmd.extend(["-m", body])
    if skip_hooks:
        cmd.append("--no-verify")
    if author:
        cmd.append(f"--author={author}")
    return cmd


def _format_spec_files(
    files: list[str],
    git_root: Path,
    *,
    working_dir: Path | None = None,
) -> None:
    """Run ``ruff check --fix`` then ``ruff format`` on *files*.

    Non-fatal: logs warnings on failure but never raises.
    Resolves paths via :func:`_resolve_repo_path` so both git-root-relative
    and package-relative inputs are handled transparently.
    """
    targets: list[str] = []
    for f in files:
        if not f.endswith(".py"):
            continue
        resolved, _tried, err = _resolve_repo_path(f, git_root, working_dir)
        if err:
            continue
        targets.append(str(resolved) if resolved is not None else str(git_root / f))
    if not targets:
        return

    for cmd in (
        ["ruff", "check", "--fix", *targets],
        ["ruff", "format", *targets],
    ):
        try:
            subprocess.run(
                cmd,
                cwd=git_root,
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
        except FileNotFoundError:
            logger.debug("ruff not found, skipping pre-commit format")
            return
        except subprocess.TimeoutExpired:
            logger.warning("%s timed out after 120s", cmd[0])
            return


@dataclass
class CommitPhaseHook:
    """Commit all changes with message ``[axm] {phase_name}``.

    Reads ``phase_name`` from *context*.  An optional
    ``message_format`` can be provided via *params*
    (default ``"[axm] {phase}"``).  Skips gracefully when
    there is nothing to commit or no git repository.

    When ``from_outputs=True`` is passed in *params*, reads
    ``commit_spec`` from *context* instead: ``{message, body?, files}``.
    Only the listed files are staged (no ``git add -A``).
    """

    def execute(self, context: dict[str, object], **params: object) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary.
            **params: Optional ``message_format``, ``from_outputs``,
                ``working_dir``, ``skip_hooks`` (default ``False`` for
                ``from_outputs`` mode — pass ``True`` to append
                ``--no-verify`` and bypass project pre-commit hooks).

        Returns:
            HookResult with ``commit`` hash and ``message`` in metadata.
        """
        wd_raw = params.get("working_dir", context.get("working_dir", "."))
        working_dir = Path(cast("str | Path", wd_raw))

        if not params.get("enabled", True):
            return HookResult.ok(skipped=True, reason="git disabled")

        if find_git_root(working_dir) is None:
            return HookResult.ok(skipped=True, reason="not a git repo")

        profile = cast("str | None", params.pop("profile", None))

        if params.get("from_outputs"):
            skip_hooks = bool(params.get("skip_hooks", False))
            return self.commit_from_outputs(
                context, working_dir, skip_hooks=skip_hooks, profile=profile
            )

        return self._commit_legacy(context, working_dir, profile=profile, **params)

    def _commit_legacy(
        self,
        context: dict[str, object],
        working_dir: Path,
        *,
        profile: str | None = None,
        **params: object,
    ) -> HookResult:
        """Legacy mode: stage all changes and commit with a format string.

        Resolves the author identity via :func:`resolve_identity` and
        injects ``--author`` into the commit command when a profile is
        found.  Identity metadata (name, email) is included in the
        returned :class:`HookResult`.

        Args:
            context: Session context containing ``phase_name``.
            working_dir: Repository working directory.
            profile: Optional identity profile name override.
            **params: Extra params; ``message_format`` controls the
                commit message template (default ``"[axm] {phase}"``).
        """
        phase_name = cast("str", context["phase_name"])

        # Resolve author identity
        identity = resolve_identity(working_dir, profile_override=profile)
        author = f"{identity.name} <{identity.email}>" if identity else None

        # Stage all changes (scoped to working_dir for workspace layouts)
        run_git(["add", "-A", "."], working_dir)

        # Check if there's anything to commit
        status = run_git(["status", "--porcelain", "--", "."], working_dir)
        if not status.stdout.strip():
            return HookResult.ok(skipped=True, reason="nothing to commit")

        # Commit
        message_format = cast("str", params.get("message_format", "[axm] {phase}"))
        msg = message_format.format(phase=phase_name)
        commit_cmd = build_commit_cmd(msg, None, author=author)
        result = run_git(commit_cmd, working_dir)
        if result.returncode != 0:
            return HookResult.fail(f"git commit failed: {result.stderr}")

        # Get commit hash
        hash_result = run_git(["rev-parse", "--short", "HEAD"], working_dir)
        result_kw: dict[str, str] = {
            "commit": hash_result.stdout.strip(),
            "message": msg,
        }
        if identity:
            result_kw["author_name"] = identity.name
            result_kw["author_email"] = identity.email
        return HookResult.ok(**result_kw)

    def commit_from_outputs(
        self,
        context: dict[str, object],
        working_dir: Path,
        *,
        skip_hooks: bool = False,
        profile: str | None = None,
    ) -> HookResult:
        """Outputs mode: read ``commit_spec`` from context, stage listed files.

        Resolves the author identity via :func:`resolve_identity` and
        injects ``--author`` into the commit command when a profile is
        found.  If the commit fails because pre-commit hooks auto-fixed
        files (stderr contains ``"files were modified"``), the listed
        files are re-staged and the commit is retried once.

        Args:
            context: Session context containing ``commit_spec``.
            working_dir: Repository working directory.
            skip_hooks: When *True*, append ``--no-verify`` to bypass
                project pre-commit hooks.  Defaults to ``False`` so
                hooks run and surface failures via ``HookResult.fail``.
            profile: Optional identity profile name override.
        """
        spec, err = validate_commit_spec(
            cast("dict[str, object] | None", context.get("commit_spec"))
        )
        if err:
            return HookResult.fail(err)
        # spec is guaranteed non-None when err is None
        spec = cast("dict[str, object]", spec)

        files = cast("list[str]", spec["files"])
        message = cast("str", spec["message"])
        body = cast("str | None", spec.get("body"))

        git_root = find_git_root(working_dir) or working_dir

        # Resolve author identity
        identity = resolve_identity(git_root, profile_override=profile)
        author = f"{identity.name} <{identity.email}>" if identity else None

        _format_spec_files(files, git_root, working_dir=working_dir)

        warnings: list[str] = []
        stage_err = stage_spec_files(
            files, git_root, working_dir=working_dir, warnings=warnings
        )
        if stage_err:
            return HookResult.fail(stage_err)

        # Check if there's anything to commit
        status = run_git(["diff", "--cached", "--name-only"], git_root)
        if not status.stdout.strip():
            return HookResult.ok(skipped=True, reason="nothing to commit")

        commit_cmd = build_commit_cmd(
            message, body, skip_hooks=skip_hooks, author=author
        )

        result: _GitResultLike = run_git(commit_cmd, git_root)
        if result.returncode != 0:
            result = retry_commit_on_autofix(
                files, commit_cmd, git_root, result, working_dir=working_dir
            )
            if result.returncode != 0:
                return HookResult.fail(f"git commit failed: {result.stderr}")

        return build_commit_result(git_root, message, identity, warnings)
