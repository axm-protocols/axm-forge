"""Ruff diagnostic filtering for batch_edit's post-apply lint step.

``batch_edit`` runs ``ruff --fix`` over the files it touched and reports
the diagnostics ruff could not auto-fix. This module holds the helper
that strips ruff's summary noise from that output so only real
diagnostic lines remain.
"""

from __future__ import annotations

import shutil

__all__ = ["filter_ruff_lines"]

_RUFF_NOISE_PREFIXES = ("Found ", "[*] ", "No fixes")

# Tool availability — checked once at import time. Patched in tests.
_has_ruff: bool = shutil.which("ruff") is not None


def filter_ruff_lines(stdout: str) -> list[str]:
    """Keep real diagnostic lines, dropping ruff summary noise."""
    return [
        line
        for line in stdout.strip().splitlines()
        if line.strip() and not line.startswith(_RUFF_NOISE_PREFIXES)
    ]
