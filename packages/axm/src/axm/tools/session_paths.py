from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from axm.tools.write_scope import WriteContract

__all__ = ["resolve_session_paths"]

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


def _resolve(raw: str, base: Path | None, contract: WriteContract | None) -> str:
    candidate = Path(raw)
    aliased = False
    if contract is not None and candidate.is_absolute():
        for source, target in contract.read_path_aliases:
            if candidate.is_relative_to(source):
                candidate = Path(target) / candidate.relative_to(source)
                aliased = True
                break
    relative = not candidate.is_absolute()
    if relative and base is None:
        raise ValueError("relative paths require a session execution_root")
    resolved = (
        base / candidate if relative and base is not None else candidate
    ).resolve()
    boundary = Path(contract.execution_root) if contract is not None else None
    scoped = (
        aliased
        or relative
        or (boundary is not None and candidate.is_relative_to(boundary))
    )
    if scoped and contract is not None and not contract.readable(str(resolved)):
        raise ValueError(
            f"path escapes session execution_root {boundary}: {raw} -> {resolved}"
        )
    return str(resolved)


def _children(
    value: object, base: Path | None, contract: WriteContract | None
) -> object:
    if isinstance(value, Path):
        return Path(_resolve(str(value), base, contract))
    if isinstance(value, str):
        return _resolve(value, base, contract)
    if isinstance(value, list):
        return [_children(item, base, contract) for item in value]
    return value


def resolve_session_paths(
    payload: dict[str, object],
    defaults: Mapping[str, object],
    contract: WriteContract | None,
) -> None:
    """Canonicalize the payload consumed by both authorization and execution."""
    root = Path(contract.execution_root).resolve() if contract is not None else None
    for key, default in defaults.items():
        payload.setdefault(key, default)
    for key in tuple(
        key
        for key in payload
        if key in _ROOT_KEYS or key.endswith(("_path", "_root", "_dir", "_paths"))
    ):
        payload[key] = _children(payload[key], root, contract)
    raw_base = payload.get("path")
    base = Path(raw_base) if isinstance(raw_base, str) and root is not None else root
    for key in {"file", "files"} & payload.keys():
        payload[key] = _children(payload[key], base, contract)
    operations = payload.get("operations")
    if isinstance(operations, list):
        payload["operations"] = [
            {**op, "file": _children(op["file"], base, contract)}
            if isinstance(op, dict) and "file" in op
            else op
            for op in operations
        ]
