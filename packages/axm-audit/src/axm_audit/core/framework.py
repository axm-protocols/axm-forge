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

    ``node`` is the JS/TS base layer (ESLint, tsc, vitest, package.json …).
    ``svelte`` and ``react`` are UI-framework specializations that *inherit*
    the node layer and add their own rules (see :func:`resolve_frameworks`).
    Adding a new UI framework (vue, solid …) is one enum member + one
    ``resolve_frameworks`` branch + a ``rules/<fw>/`` package — no refactor.
    """

    PYTHON = "python"
    NODE = "node"
    SVELTE = "svelte"
    REACT = "react"


# UI frameworks that sit on top of the shared ``node`` base layer. Each runs the
# node rules first, then its own delta. Frame this as data so a new UI framework
# is a one-line addition.
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
    """Return True if the project shows a Svelte fingerprint.

    A Svelte project ships a ``svelte.config.{js,ts}`` or declares ``svelte``
    in its (dev)dependencies.
    """
    for cfg in ("svelte.config.js", "svelte.config.ts"):
        if (project_path / cfg).is_file():
            return True
    return _has_dependency(data, "svelte")


def _has_react_marker(data: dict[str, object]) -> bool:
    """Return True if the project declares ``react`` in its (dev)dependencies."""
    return _has_dependency(data, "react")


def detect_framework(project_path: Path) -> Framework:
    """Detect the framework of *project_path* from its manifest markers.

    Detection order (conservative — defaults to Python):

    1. ``package.json`` + Svelte marker → :attr:`Framework.SVELTE`
    2. ``package.json`` + React marker → :attr:`Framework.REACT`
    3. ``package.json`` alone → :attr:`Framework.NODE`
    4. otherwise (``pyproject.toml`` or nothing) → :attr:`Framework.PYTHON`

    Svelte wins over React when both are present (a SvelteKit app may pull a
    react-named transitive tool); per-package detection in a monorepo happens
    downstream.

    Args:
        project_path: Project (or package) root directory.

    Returns:
        The detected :class:`Framework`.
    """
    if not (project_path / "package.json").is_file():
        return Framework.PYTHON
    # A package.json is present → this is a node project. An unparsable manifest
    # still resolves to node (never python); we just can't read its UI marker.
    data = _read_package_json(project_path) or {}
    if _has_svelte_marker(project_path, data):
        return Framework.SVELTE
    if _has_react_marker(data):
        return Framework.REACT
    return Framework.NODE


def resolve_frameworks(framework: Framework) -> tuple[Framework, ...]:
    """Expand a framework to the chain of rule-sets it should run.

    A UI framework (``svelte``, ``react``) runs the shared ``node`` rules
    first, then its own delta. ``node`` and ``python`` run only their own.

    Args:
        framework: The leaf framework to resolve.

    Returns:
        Tuple of frameworks whose rules apply, base first.
    """
    if framework in _NODE_UI_FRAMEWORKS:
        return (Framework.NODE, framework)
    return (framework,)
