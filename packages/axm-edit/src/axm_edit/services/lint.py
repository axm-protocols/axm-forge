"""Ruff diagnostic filtering + availability probing for batch_edit's lint step.

``batch_edit`` runs ``ruff --fix`` over the files it touched and reports
the diagnostics ruff could not auto-fix. This module holds the helper
that strips ruff's summary noise from that output so only real
diagnostic lines remain, plus the availability probe that decides whether
the lint step runs at all.

Availability is probed *per target root* by shelling ``uv run ruff
--version`` with ``cwd=root`` — this detects an env-local ruff even when
no global ruff is on ``PATH``. Results are memoized per resolved root so
repeated edits against the same project do not re-spawn the probe, while a
different root re-probes.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

__all__ = ["filter_ruff_lines", "ruff_available"]

_RUFF_NOISE_PREFIXES = ("Found ", "[*] ", "No fixes")

# Per-root availability cache: resolved absolute root -> ruff available?
_RUFF_AVAILABLE_CACHE: dict[Path, bool] = {}


def ruff_available(root: Path) -> bool:
    """Return whether ruff can run inside *root*'s environment.

    Probes ``uv run ruff --version`` with ``cwd=root`` and treats ruff as
    available iff the subprocess returns 0. A missing ``uv``/ruff binary
    (``FileNotFoundError``) or any OS-level failure counts as *absent* (a
    clean skip), never as a crash. The verdict is memoized on the resolved
    absolute root; a distinct root re-probes.
    """
    resolved = Path(root).resolve()
    cached = _RUFF_AVAILABLE_CACHE.get(resolved)
    if cached is not None:
        return cached

    try:
        result = subprocess.run(
            ["uv", "run", "ruff", "--version"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        available = result.returncode == 0
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        available = False

    _RUFF_AVAILABLE_CACHE[resolved] = available
    return available


def filter_ruff_lines(stdout: str) -> list[str]:
    """Keep real diagnostic lines, dropping ruff summary noise."""
    return [
        line
        for line in stdout.strip().splitlines()
        if line.strip() and not line.startswith(_RUFF_NOISE_PREFIXES)
    ]
