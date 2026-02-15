"""Commit-phase hook action.

Stages all changes and commits with ``[axm] {phase_name}``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm_engine.services.hooks.base import HookResult

from axm_git.core.runner import run_git

__all__ = ["CommitPhaseHook"]


@dataclass
class CommitPhaseHook:
    """Commit all changes with message ``[axm] {phase_name}``.

    Reads ``phase_name`` from *context*.  An optional
    ``message_format`` can be provided via *params*
    (default ``"[axm] {phase}"``).  Skips gracefully when
    there is nothing to commit or no git repository.
    """

    def execute(self, context: dict[str, Any], **params: Any) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary (must contain ``phase_name``).
            **params: Optional ``message_format`` (default ``"[axm] {phase}"``).

        Returns:
            HookResult with ``commit`` hash and ``message`` in metadata.
        """
        working_dir = Path(context.get("working_dir", "."))
        phase_name: str = context["phase_name"]

        if not (working_dir / ".git").exists():
            return HookResult.ok(skipped=True, reason="not a git repo")

        # Stage all changes
        run_git(["add", "-A"], working_dir)

        # Check if there's anything to commit
        status = run_git(["status", "--porcelain"], working_dir)
        if not status.stdout.strip():
            return HookResult.ok(skipped=True, reason="nothing to commit")

        # Commit
        msg = params.get("message_format", "[axm] {phase}").format(
            phase=phase_name,
        )
        result = run_git(["commit", "-m", msg], working_dir)
        if result.returncode != 0:
            return HookResult.fail(f"git commit failed: {result.stderr}")

        # Get commit hash
        hash_result = run_git(["rev-parse", "--short", "HEAD"], working_dir)
        return HookResult.ok(commit=hash_result.stdout.strip(), message=msg)
