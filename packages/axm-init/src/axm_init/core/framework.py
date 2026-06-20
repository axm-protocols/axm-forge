"""Framework detection for the gold-standard checker.

Mirror of ``axm_audit.core.framework`` (kept local so the two packages stay
independent — a future refactor could host this in ``axm-ingot`` and have both
import it). Decides which set of ``check_*`` functions ``CheckEngine`` runs.

``node`` is the JS/TS base layer; ``svelte`` and ``react`` are UI-framework
specializations that inherit it (see :func:`resolve_frameworks`).
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path

__all__ = ["Framework", "detect_framework", "resolve_frameworks"]


class Framework(StrEnum):
    """Ecosystem a project is scaffolded/checked against."""

    PYTHON = "python"
    NODE = "node"
    SVELTE = "svelte"
    REACT = "react"


_NODE_UI_FRAMEWORKS: frozenset[Framework] = frozenset(
    {Framework.SVELTE, Framework.REACT}
)


def _read_package_json(project_path: Path) -> dict[str, object] | None:
    """Load ``package.json`` as a dict, or ``None`` if absent/invalid."""
    pkg = project_path / "package.json"
    if not pkg.is_file():
        return None
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _has_dependency(data: dict[str, object], name: str) -> bool:
    """Return True if *name* is declared in (dev)dependencies of *data*."""
    for key in ("dependencies", "devDependencies"):
        section = data.get(key)
        if isinstance(section, dict) and name in section:
            return True
    return False


def _has_svelte_marker(project_path: Path, data: dict[str, object]) -> bool:
    """Return True if the project shows a Svelte fingerprint."""
    for cfg in ("svelte.config.js", "svelte.config.ts"):
        if (project_path / cfg).is_file():
            return True
    return _has_dependency(data, "svelte")


def detect_framework(project_path: Path) -> Framework:
    """Detect the framework of *project_path* from its manifest markers.

    ``package.json`` + svelte → ``svelte``; + react → ``react``; alone →
    ``node``; otherwise → ``python`` (conservative default).

    Args:
        project_path: Project root directory.

    Returns:
        The detected :class:`Framework`.
    """
    if not (project_path / "package.json").is_file():
        return Framework.PYTHON
    # A package.json is present → node project even if the manifest is unparsable
    # (we just can't read its UI marker then).
    data = _read_package_json(project_path) or {}
    if _has_svelte_marker(project_path, data):
        return Framework.SVELTE
    if _has_dependency(data, "react"):
        return Framework.REACT
    return Framework.NODE


def resolve_frameworks(framework: Framework) -> tuple[Framework, ...]:
    """Expand a framework to the chain of check-sets it should run.

    A UI framework (``svelte``, ``react``) runs the shared ``node`` checks
    first, then its own delta. ``node`` and ``python`` run only their own.

    Args:
        framework: The leaf framework to resolve.

    Returns:
        Tuple of frameworks whose checks apply, base first.
    """
    if framework in _NODE_UI_FRAMEWORKS:
        return (Framework.NODE, framework)
    return (framework,)
