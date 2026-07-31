from __future__ import annotations

import re
from pathlib import Path

__all__ = [
    "canonical_suite_name",
    "is_suite_name",
    "is_suite_path",
    "resolve_suite_dir",
]

_PROJECT_SEPARATOR = re.compile(r"[-.]+")


def canonical_suite_name(project_root: str | Path) -> str:
    """Return the namespaced test-suite directory for a project directory."""
    project_name = Path(project_root).name
    normalized = _PROJECT_SEPARATOR.sub("_", project_name)
    return f"tests_{normalized}"


def is_suite_name(name: str) -> bool:
    """Return whether *name* denotes a legacy or namespaced suite root."""
    return name == "tests" or (name.startswith("tests_") and len(name) > len("tests_"))


def is_suite_path(path: str | Path) -> bool:
    """Return whether any component of *path* is a recognized suite root."""
    return any(is_suite_name(part) for part in Path(path).parts)


def resolve_suite_dir(project_root: str | Path) -> Path | None:
    """Resolve a project's suite root, preferring its namespaced directory."""
    root = Path(project_root)
    canonical = root / canonical_suite_name(root)
    if canonical.is_dir():
        return canonical

    legacy = root / "tests"
    if legacy.is_dir():
        return legacy
    return None
