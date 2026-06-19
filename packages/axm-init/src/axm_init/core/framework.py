"""Framework detection for the gold-standard checker.

Mirror of ``axm_audit.core.framework`` (kept local so the two packages stay
independent — a future refactor could host this in ``axm-ingot`` and have both
import it). Decides which set of ``check_*`` functions ``CheckEngine`` runs.
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path

__all__ = ["Framework", "detect_framework"]


class Framework(StrEnum):
    """Ecosystem a project is scaffolded/checked against."""

    PYTHON = "python"
    NODE = "node"
    SVELTE = "svelte"


def _has_svelte_marker(project_path: Path) -> bool:
    """Return True if the project shows a Svelte fingerprint."""
    for cfg in ("svelte.config.js", "svelte.config.ts"):
        if (project_path / cfg).is_file():
            return True
    pkg = project_path / "package.json"
    if not pkg.is_file():
        return False
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    for key in ("dependencies", "devDependencies"):
        section = data.get(key)
        if isinstance(section, dict) and "svelte" in section:
            return True
    return False


def detect_framework(project_path: Path) -> Framework:
    """Detect the framework of *project_path* from its manifest markers.

    ``package.json`` + Svelte marker → ``svelte``; ``package.json`` alone →
    ``node``; otherwise → ``python`` (conservative default).

    Args:
        project_path: Project root directory.

    Returns:
        The detected :class:`Framework`.
    """
    if (project_path / "package.json").is_file():
        return Framework.SVELTE if _has_svelte_marker(project_path) else Framework.NODE
    return Framework.PYTHON
