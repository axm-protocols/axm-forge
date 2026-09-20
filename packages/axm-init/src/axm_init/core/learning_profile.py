from __future__ import annotations

from pathlib import Path
from typing import cast

from tomlkit import array, dumps, parse
from tomlkit.container import OutOfOrderTableProxy
from tomlkit.items import Array, Table

from axm_init.core.root_lock import target_root_lock
from axm_init.core.toml_edit import table_at

__all__ = [
    "declared_learning_domain",
    "merge_learning_metadata",
    "register_learning_profile",
]

_LEARNING_DISTRIBUTIONS = ("axm-learning", "axm-fit", "axm-tune")
_COMPOSED_LEARNING_DISTRIBUTIONS = (
    "axm==0.9.0",
    "numpy==2.5.3",
    "torch==2.14.0",
)
_SCHEMA_VERSION = 1


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
    if not isinstance(tool, (Table, OutOfOrderTableProxy)):
        return None
    axm_init = cast(Table, tool).get("axm-init")
    if not isinstance(axm_init, Table):
        return None
    profile = axm_init.get("learning")
    if not isinstance(profile, Table):
        return None
    domain = profile.get("domain")
    return domain if isinstance(domain, str) else None


def merge_learning_metadata(metadata: str, domain: str, module_name: str) -> str:
    """Merge the learning profile into project metadata without re-rendering it."""
    document = parse(metadata)
    project = table_at(document, "project")
    dependencies = _array_at(project, "dependencies")
    distributions = (
        _COMPOSED_LEARNING_DISTRIBUTIONS
        if document.get("dependency-groups") is not None
        else _LEARNING_DISTRIBUTIONS
    )
    for distribution in distributions:
        if distribution not in dependencies:
            dependencies.append(distribution)

    entry_points = table_at(project, "entry-points")
    axm_tools = table_at(entry_points, "axm.tools")
    axm_tools[f"{module_name}_train"] = f"{module_name}.learning.tool:TrainingTool"

    tool_item = document.get("tool")
    if tool_item is None:
        tool = table_at(document, "tool")
    elif isinstance(tool_item, (Table, OutOfOrderTableProxy)):
        tool = cast(Table, tool_item)
    else:
        msg = "'tool' must be a TOML table"
        raise ValueError(msg)
    axm_init = table_at(tool, "axm-init")
    profile = table_at(axm_init, "learning")
    profile["schema_version"] = _SCHEMA_VERSION
    profile["domain"] = domain
    return dumps(document)


def declared_learning_domain(
    root: Path,
    requested_domain: str | None = None,
) -> str | None:
    """Return the learning domain declared by the project at *root*, if any."""
    canonical_root = root.resolve()
    with target_root_lock(canonical_root):
        metadata_path = canonical_root / "pyproject.toml"
        if not metadata_path.is_file():
            return None
        existing_domain = _learning_domain(metadata_path.read_text(encoding="utf-8"))
        if (
            requested_domain is not None
            and existing_domain is not None
            and existing_domain != requested_domain
        ):
            msg = (
                "learning profile domain conflict: "
                f"existing {existing_domain!r}, requested {requested_domain!r}"
            )
            raise ValueError(msg)
        return existing_domain


def register_learning_profile(root: Path, domain: str, module_name: str) -> None:
    """Persist one learning profile while serializing writes on its root."""
    canonical_root = root.resolve()
    with target_root_lock(canonical_root):
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
