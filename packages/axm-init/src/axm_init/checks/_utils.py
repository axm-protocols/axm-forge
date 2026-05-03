"""Shared utilities for audit check modules."""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from axm_init.models.check import CheckResult

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

__all__ = [
    "load_exclusions",
    "load_toml",
    "load_toml_with_workspace_fallback",
    "merge_tool_sections",
    "requires_toml",
]


def load_toml(project: Path) -> dict[str, Any] | None:
    """Load pyproject.toml, return None if missing/corrupt."""
    path = project / "pyproject.toml"
    if not path.exists():
        return None
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except Exception:
        return None


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *override* into *base*; override wins on conflicts.

    Only ``dict`` values are merged recursively.  All other types (lists,
    strings, bools, …) are replaced wholesale by the override value.
    """
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def merge_tool_sections(
    base: dict[str, Any],
    override: dict[str, Any],
) -> dict[str, Any]:
    """Deep-merge tool sections: *override* wins at leaf level.

    For each tool key (ruff, mypy, coverage, …), nested dicts are merged
    recursively so that both root and member settings are preserved.
    Non-dict values use the override if present, else the base.
    Non-tool keys always come from *override*.
    """
    merged = dict(override)
    base_tool = base.get("tool", {})
    override_tool = override.get("tool", {})
    if not base_tool:
        return merged
    combined_tool = _deep_merge(base_tool, override_tool)
    merged["tool"] = combined_tool
    return merged


def load_toml_with_workspace_fallback(project: Path) -> dict[str, Any] | None:
    """Load pyproject.toml, merging workspace root tool sections for members.

    When *project* is a UV workspace member, the workspace root's tool
    sections are used as a base layer.  The member's own tool sections
    override on top (per top-level tool key).
    """
    from axm_init.checks._workspace import find_workspace_root

    data = load_toml(project)
    if data is None:
        return None

    workspace_root = find_workspace_root(project)
    if workspace_root is None or workspace_root == project:
        return data

    root_data = load_toml(workspace_root)
    if root_data is None:
        return data

    return merge_tool_sections(root_data, data)


def requires_toml(
    check_name: str,
    category: str,
    weight: int,
    fix: str,
) -> Callable[
    [Callable[[Path, dict[str, Any]], CheckResult]],
    Callable[[Path], CheckResult],
]:
    """Decorator that loads pyproject.toml and passes data to the check.

    If pyproject.toml is missing or unparsable, returns a failure
    ``CheckResult`` immediately — eliminating the repeated null-guard
    preamble from every check function.

    The decorated function receives ``(project, data)`` instead of just
    ``(project)`` — where ``data`` is the parsed TOML dict.

    Args:
        check_name: Check result name (e.g. ``"pyproject.ruff"``).
        category: Category key (e.g. ``"pyproject"``).
        weight: Points weight for this check.
        fix: Fix message for the "not found" failure.
    """

    def decorator(
        fn: Callable[[Path, dict[str, Any]], CheckResult],
    ) -> Callable[[Path], CheckResult]:
        """Wrap a check function with TOML pre-loading."""

        @functools.wraps(fn)
        def wrapper(project: Path) -> CheckResult:
            """Load TOML then delegate to the wrapped check."""
            data = load_toml_with_workspace_fallback(project)
            if data is None:
                return CheckResult(
                    name=check_name,
                    category=category,
                    passed=False,
                    weight=weight,
                    message="pyproject.toml not found or unparsable",
                    details=[],
                    fix=fix,
                )
            return fn(project, data)

        return wrapper

    return decorator


def load_exclusions(project: Path) -> set[str]:
    """Load per-package check exclusions from pyproject.toml.

    Reads the ``[tool.axm-init].exclude`` key and returns check name
    prefixes that should be auto-passed for this package.

    Example config::

        [tool.axm-init]
        exclude = ["cli", "changelog", "deps.entry_points"]

    Args:
        project: Path to the project root containing ``pyproject.toml``.

    Returns:
        Set of check name prefixes to exclude.  Empty set if no
        exclusions are configured.
    """
    data = load_toml(project)
    if data is None:
        return set()

    axm_init_config: dict[str, Any] = data.get("tool", {}).get("axm-init", {})
    if not axm_init_config:
        return set()

    raw = axm_init_config.get("exclude")
    if raw is None:
        return set()

    # Handle string → wrap in list
    if isinstance(raw, str):
        raw = [raw]

    if not isinstance(raw, list):
        logger.warning(
            "Invalid [tool.axm-init].exclude value (expected list): %r",
            raw,
        )
        return set()

    exclusions: set[str] = set()
    for item in raw:
        if isinstance(item, str) and item:
            exclusions.add(item)
        else:
            logger.warning(
                "Invalid exclusion entry in [tool.axm-init].exclude: %r",
                item,
            )

    return exclusions
