"""Best-effort persistence of audit quality snapshots.

Each ``audit`` run appends one JSON line to ``~/axm/quality/{package}.jsonl``
capturing the score, grade and the list of actionable failures, stamped with a
UTC timestamp and the current git HEAD.

The file is an append-only history: the *current* state of a repo is the last
line of a given ``kind``; a *trend* is obtained by filtering on ``sha`` at read
time (deduplication is a reader concern, never a writer one).

Design contract: **observability must never break an audit.** Every failure
here (no git, unwritable disk, malformed payload) is swallowed — the caller's
``ToolResult`` is returned unchanged regardless.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

__all__ = ["record_quality_snapshot"]

type TraceKind = Literal["audit", "governance"]


def _quality_dir() -> Path:
    """Root directory for quality history files (``~/axm/quality``)."""
    return Path.home() / "axm" / "quality"


def _git_head(project_path: Path) -> tuple[str | None, str | None]:
    """Return ``(short_sha, branch)`` for ``project_path`` or ``(None, None)``.

    Best-effort: any git failure (not a repo, git absent) yields ``None``.
    """
    try:
        sha = _git(project_path, "--short", "HEAD")
        branch = _git(project_path, "--abbrev-ref", "HEAD")
        return (sha or None, branch or None)
    except (subprocess.SubprocessError, OSError):
        return (None, None)


def _git(project_path: Path, *rev_parse_args: str) -> str:
    """Run ``git -C <path> rev-parse <args>`` and return trimmed stdout.

    Argv is fully hardcoded (no untrusted input), so the bandit subprocess
    check (S603) does not apply.
    """
    cmd = ["git", "-C", str(project_path), "rev-parse", *rev_parse_args]
    proc = subprocess.run(  # noqa: S603
        cmd, capture_output=True, text=True, timeout=5, check=True
    )
    return proc.stdout.strip()


def normalize_fails(data: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract actionable failures from an audit/init ``data`` payload.

    ``audit`` emits ``failed: [{rule_id, message, fix_hint, ...}]``.
    ``init_check`` emits ``failures: [{name, message, fix, ...}]``.
    Both are normalized to ``{rule_id, message, fix_hint}``.
    """
    raw = data.get("failed")
    if raw is None:
        raw = data.get("failures")
    if not isinstance(raw, Sequence):
        return []
    fails: list[dict[str, object]] = []
    for entry in raw:
        if not isinstance(entry, Mapping):
            continue
        fails.append(
            {
                "rule_id": entry.get("rule_id") or entry.get("name"),
                "message": entry.get("message"),
                "fix_hint": entry.get("fix_hint") or entry.get("fix"),
            }
        )
    return fails


def record_quality_snapshot(
    *,
    path: str,
    kind: TraceKind,
    data: Mapping[str, object],
) -> None:
    """Append one quality snapshot line for ``path``; never raise.

    Args:
        path: Path to the audited project (its directory name becomes the
            history file name).
        kind: ``"audit"`` (axm-audit) or ``"governance"`` (axm-init).
        data: The ``ToolResult.data`` dict — must carry ``score``/``grade``
            and a ``failed``/``failures`` list.
    """
    try:
        project_path = Path(path).resolve()
        package = project_path.name
        sha, branch = _git_head(project_path)
        line = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "repo": package,
            "sha": sha,
            "branch": branch,
            "kind": kind,
            "score": data.get("score"),
            "grade": data.get("grade"),
            "fails": normalize_fails(data),
        }
        out_dir = _quality_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / f"{package}.jsonl"
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, default=str) + "\n")
    except Exception:  # noqa: BLE001 - observability must never break an audit
        return
