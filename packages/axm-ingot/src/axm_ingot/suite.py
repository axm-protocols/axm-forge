from __future__ import annotations

import re
import tomllib
from pathlib import Path

__all__ = [
    "canonical_suite_name",
    "is_suite_name",
    "is_suite_path",
    "resolve_suite_dir",
    "resolve_suite_dirs",
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
    """Resolve a project's primary suite root from config, then convention."""
    root = Path(project_root)
    suites = _direct_suite_dirs(root)
    return suites[0] if suites else None


def _direct_suite_dirs(root: Path) -> tuple[Path, ...]:
    """Resolve suite roots directly owned by *root*, in precedence order."""
    configured = _configured_suite_dirs(root)
    if configured:
        return configured

    canonical = root / canonical_suite_name(root)
    if canonical.is_dir():
        return (canonical,)

    legacy = root / "tests"
    if legacy.is_dir():
        return (legacy,)
    return ()


def _configured_suite_dirs(root: Path) -> tuple[Path, ...]:
    """Read existing, project-owned pytest ``testpaths`` from pyproject.toml."""
    try:
        data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return ()
    tool = data.get("tool")
    pytest_cfg = tool.get("pytest") if isinstance(tool, dict) else None
    ini = pytest_cfg.get("ini_options") if isinstance(pytest_cfg, dict) else None
    raw_paths = ini.get("testpaths") if isinstance(ini, dict) else None
    values = raw_paths if isinstance(raw_paths, list) else []
    owned: list[Path] = []
    resolved_root = root.resolve()
    for raw in values:
        if not isinstance(raw, str) or not raw.strip():
            continue
        candidate = (root / raw).resolve()
        try:
            candidate.relative_to(resolved_root)
        except ValueError:
            continue
        if candidate.is_dir() and candidate not in owned:
            owned.append(candidate)
    return tuple(owned)


def resolve_suite_dirs(project_root: str | Path) -> tuple[Path, ...]:
    """Resolve suite roots owned by a project and each uv-workspace member."""
    from axm_ingot.uv import resolve_workspace

    root = Path(project_root)
    suites: list[Path] = []
    suites.extend(_direct_suite_dirs(root))

    workspace = resolve_workspace(root)
    if workspace is None:
        return tuple(suites)

    for member in workspace.members:
        for suite in _direct_suite_dirs(member.path):
            if suite not in suites:
                suites.append(suite)
    return tuple(suites)
