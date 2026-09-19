from __future__ import annotations

import _thread
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from tomlkit import TOMLDocument, array, dumps, parse, table
from tomlkit.items import Array, Table

__all__ = [
    "declared_learning_domain",
    "merge_learning_metadata",
    "register_learning_profile",
]

_LEARNING_DISTRIBUTIONS = ("axm-learning", "axm-fit", "axm-tune")
_SCHEMA_VERSION = 1


type _TomlContainer = TOMLDocument | Table


@dataclass
class _RootLockEntry:
    lock: _thread.RLock
    users: int = 0


_ROOT_LOCKS: dict[Path, _RootLockEntry] = {}
_ROOT_LOCKS_GUARD = _thread.RLock()


def _table_at(container: _TomlContainer, key: str) -> Table:
    value = container.get(key)
    if value is None:
        created = table()
        container[key] = created
        return created
    if not isinstance(value, Table):
        msg = f"{key!r} must be a TOML table"
        raise ValueError(msg)
    return value


def _array_at(container: Table, key: str) -> Array:
    value = container.get(key)
    if value is None:
        created = array()
        container[key] = created
        return created
    if not isinstance(value, Array):
        msg = f"{key!r} must be a TOML array"
        raise ValueError(msg)
    return value


def _learning_domain(metadata: str) -> str | None:
    document = parse(metadata)
    tool = document.get("tool")
    if not isinstance(tool, Table):
        return None
    axm_init = tool.get("axm-init")
    if not isinstance(axm_init, Table):
        return None
    profile = axm_init.get("learning")
    if not isinstance(profile, Table):
        return None
    domain = profile.get("domain")
    return domain if isinstance(domain, str) else None


@contextmanager
def _target_root_lock(root: Path) -> Iterator[None]:
    canonical_root = root.resolve()
    with _ROOT_LOCKS_GUARD:
        entry = _ROOT_LOCKS.get(canonical_root)
        if entry is None:
            entry = _RootLockEntry(lock=_thread.RLock())
            _ROOT_LOCKS[canonical_root] = entry
        entry.users += 1
    entry.lock.acquire()
    try:
        yield
    finally:
        entry.lock.release()
        with _ROOT_LOCKS_GUARD:
            entry.users -= 1
            if entry.users == 0:
                _ROOT_LOCKS.pop(canonical_root, None)


def merge_learning_metadata(metadata: str, domain: str, module_name: str) -> str:
    """Merge the learning profile into project metadata without re-rendering it."""
    document = parse(metadata)
    project = _table_at(document, "project")
    dependencies = _array_at(project, "dependencies")
    for distribution in _LEARNING_DISTRIBUTIONS:
        if distribution not in dependencies:
            dependencies.append(distribution)

    entry_points = _table_at(project, "entry-points")
    axm_tools = _table_at(entry_points, "axm.tools")
    axm_tools[f"{module_name}_train"] = f"{module_name}.learning.tool:TrainingTool"

    tool = _table_at(document, "tool")
    axm_init = _table_at(tool, "axm-init")
    profile = _table_at(axm_init, "learning")
    profile["schema_version"] = _SCHEMA_VERSION
    profile["domain"] = domain
    return dumps(document)


def declared_learning_domain(root: Path) -> str | None:
    """Return the learning domain declared by the project at *root*, if any."""
    metadata_path = root / "pyproject.toml"
    if not metadata_path.is_file():
        return None
    return _learning_domain(metadata_path.read_text(encoding="utf-8"))


def register_learning_profile(root: Path, domain: str, module_name: str) -> None:
    """Persist one learning profile while serializing writes on its root."""
    canonical_root = root.resolve()
    with _target_root_lock(canonical_root):
        metadata_path = canonical_root / "pyproject.toml"
        metadata = metadata_path.read_text(encoding="utf-8")
        existing_domain = _learning_domain(metadata)
        if existing_domain is not None and existing_domain != domain:
            msg = (
                "learning profile domain conflict: "
                f"existing {existing_domain!r}, requested {domain!r}"
            )
            raise ValueError(msg)
        merged = merge_learning_metadata(metadata, domain, module_name)
        metadata_path.write_text(merged, encoding="utf-8")
