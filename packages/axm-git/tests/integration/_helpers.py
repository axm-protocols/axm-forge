"""Shared helpers for ``tests/integration``.

Promoted from duplicate top-level defs found across files.
Import explicitly: ``from tests.integration._helpers import <name>``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace


def _git_result(
    stdout: str = "", stderr: str = "", returncode: int = 0
) -> SimpleNamespace:
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def _make_context(
    repo: Path,
    ticket_id: str = "AXM-42",
    title: str = "feat(git): worktree hooks",
    labels: list[str] | None = None,
) -> dict[str, str | list[str]]:
    return {
        "repo_path": str(repo),
        "ticket_id": ticket_id,
        "ticket_title": title,
        "ticket_labels": labels if labels is not None else ["worktree"],
    }
