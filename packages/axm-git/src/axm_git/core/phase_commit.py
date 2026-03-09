"""Retrieve commit hashes for AXM protocol phases."""

from __future__ import annotations

from pathlib import Path

from axm_git.core.runner import run_git

__all__ = ["get_phase_commit"]


def get_phase_commit(
    working_dir: Path,
    phase_name: str,
    *,
    message_format: str = "[axm] {phase}",
) -> str | None:
    """Retrieve the commit hash associated with an AXM phase.

    Searches git log for commits whose message matches the format
    used by :class:`CommitPhaseHook`.

    Args:
        working_dir: Repository root path.
        phase_name: Phase name to search for.
        message_format: Message pattern used by CommitPhaseHook
            (default ``"[axm] {phase}"``).

    Returns:
        Short commit hash if found, ``None`` otherwise.
    """
    if not (working_dir / ".git").exists():
        return None

    needle = message_format.format(phase=phase_name)
    result = run_git(
        ["log", "--oneline", "--grep", needle, "--format=%h", "-1"],
        working_dir,
    )
    sha = result.stdout.strip()
    return sha if sha else None
