"""Session-local path preparation for both MCP exposure routes."""

from __future__ import annotations

import inspect
from collections.abc import Mapping

from axm.tools.write_scope import WriteContract

__all__ = ["path_defaults", "resolve_session_paths"]

_ROOT_KEYS = frozenset(
    {
        "path",
        "root",
        "repo_path",
        "project_path",
        "target_path",
        "worktree_path",
        "destination",
        "cwd",
        "dest",
        "directory",
        "paths",
    }
)


def _is_root_key(name: str) -> bool:
    return name in _ROOT_KEYS or name.endswith(("_path", "_root", "_dir", "_paths"))


def path_defaults(fn: object) -> dict[str, object]:
    """Retain implicit filesystem roots from the tool's invocation signature."""
    if not callable(fn):
        return {}
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return {}
    return {
        name: param.default
        for name, param in params.items()
        if _is_root_key(name)
        and param.default is not inspect.Parameter.empty
        and param.default is not None
    }


def resolve_session_paths(
    payload: dict[str, object],
    defaults: Mapping[str, object],
    contract: WriteContract | None,
) -> None:
    """Canonicalize once in place; authorization and execution consume this payload.

    Never changes process cwd or environment: concurrent sessions retain independent
    bases. Absolute read roots may name external dependencies; mutation authorization
    subsequently enforces the write perimeter.
    """
    from axm.tools.session_paths import resolve_session_paths as resolve_shared

    resolve_shared(payload, defaults, contract)
