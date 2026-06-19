"""Framework detection — which ecosystem a project belongs to.

The audit registry is indexed by ``(category, framework)``. A project is
audited against the rules of its detected (or explicitly requested) framework.
``svelte`` inherits ``node`` (a Svelte project runs the node rules *plus* the
svelte-specific ones).

Dependency-free: stdlib + a tiny TOML/JSON read. Imported by ``base`` and
``auditor`` without creating cycles.
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path

__all__ = ["Framework", "detect_framework", "resolve_frameworks"]


class Framework(StrEnum):
    """Ecosystem a project is written in.

    ``svelte`` is a specialization of ``node`` (see :func:`resolve_frameworks`).
    """

    PYTHON = "python"
    NODE = "node"
    SVELTE = "svelte"


def _has_svelte_marker(project_path: Path) -> bool:
    """Return True if the project shows a Svelte fingerprint.

    A Svelte project is a node project that either ships a
    ``svelte.config.{js,ts}`` or declares ``svelte`` in its
    (dev)dependencies.
    """
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

    Detection order (conservative — defaults to Python):

    1. ``package.json`` with a Svelte marker → :attr:`Framework.SVELTE`
    2. ``package.json`` without a Svelte marker → :attr:`Framework.NODE`
    3. otherwise (``pyproject.toml`` or nothing) → :attr:`Framework.PYTHON`

    A monorepo root with no manifest of its own resolves to ``python`` unless a
    ``package.json`` sits at the root; per-package detection happens downstream.

    Args:
        project_path: Project (or package) root directory.

    Returns:
        The detected :class:`Framework`.
    """
    if (project_path / "package.json").is_file():
        return Framework.SVELTE if _has_svelte_marker(project_path) else Framework.NODE
    return Framework.PYTHON


def resolve_frameworks(framework: Framework) -> tuple[Framework, ...]:
    """Expand a framework to the chain of rule-sets it should run.

    ``svelte`` runs both the ``node`` rules and the ``svelte`` rules;
    ``node`` and ``python`` run only their own.

    Args:
        framework: The leaf framework to resolve.

    Returns:
        Tuple of frameworks whose rules apply, base first.
    """
    if framework is Framework.SVELTE:
        return (Framework.NODE, Framework.SVELTE)
    return (framework,)
