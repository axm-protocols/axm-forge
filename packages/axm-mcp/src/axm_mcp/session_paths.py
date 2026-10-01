"""Session-local path preparation for both MCP exposure routes."""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from pathlib import Path

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
_CHILD_KEYS = frozenset({"file", "files"})


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


def _resolve(raw: str, base: Path | None, boundary: Path | None) -> str:
    candidate = Path(raw)
    relative = not candidate.is_absolute()
    if relative and base is None:
        raise ValueError("relative paths require a session execution_root")
    resolved = (
        base / candidate if relative and base is not None else candidate
    ).resolve()
    scoped = relative or (boundary is not None and candidate.is_relative_to(boundary))
    if scoped and boundary is not None and not resolved.is_relative_to(boundary):
        from axm.tools.dependency_reads import session_readable

        if session_readable(resolved):
            return str(resolved)
        raise ValueError(
            f"path escapes session execution_root {boundary}: {raw} -> {resolved}"
        )
    return str(resolved)


def _children(value: object, base: Path | None, boundary: Path | None) -> object:
    if isinstance(value, Path):
        return Path(_resolve(str(value), base, boundary))
    if isinstance(value, str):
        return _resolve(value, base, boundary)
    if isinstance(value, list):
        return [_children(item, base, boundary) for item in value]
    return value


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
    root = Path(contract.execution_root).resolve() if contract is not None else None
    for key, default in defaults.items():
        payload.setdefault(key, default)
    for key in tuple(key for key in payload if _is_root_key(key)):
        value = payload[key]
        payload[key] = _children(value, root, root)
    raw_base = payload.get("path")
    base = Path(raw_base) if isinstance(raw_base, str) and root is not None else root
    for key in _CHILD_KEYS & payload.keys():
        payload[key] = _children(payload[key], base, root)
    operations = payload.get("operations")
    if isinstance(operations, list):
        payload["operations"] = [
            {**op, "file": _children(op["file"], base, root)}
            if isinstance(op, dict) and "file" in op
            else op
            for op in operations
        ]
