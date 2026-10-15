"""Build a deterministic, read-only workspace release plan."""

from __future__ import annotations

from graphlib import CycleError, TopologicalSorter
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from axm_git.core.release_inventory import (
    Package,
    ReleaseInventory,
    git_output,
    read_inventory,
)
from axm_git.core.runner import run_git
from axm_git.core.semver import parse_tag, release_suggestion

__all__ = ["plan_releases", "release_order"]


def release_order(packages: tuple[Package, ...]) -> list[str]:
    """Order mandatory prerequisites first, with stable independent-node ties."""
    names = {p.name for p in packages}
    graph = {
        p.name: {canonicalize_name(Requirement(r).name) for r in p.required} & names
        for p in packages
    }
    try:
        sorter = TopologicalSorter(graph)
        sorter.prepare()
    except CycleError as exc:
        raise ValueError(f"Mandatory release dependency cycle: {exc.args[1]}") from exc
    order = []
    while sorter.is_active():
        ready = sorted(sorter.get_ready())
        order.extend(ready)
        sorter.done(*ready)
    return order


def _changed(inventory: ReleaseInventory, package: Package, tag: str) -> bool:
    result = run_git(
        ["diff", "--quiet", tag, inventory.ref, "--", package.path], inventory.root
    )
    if result.returncode not in (0, 1):
        raise ValueError(result.stderr.strip() or "git diff failed")
    return result.returncode == 1


def _basis(
    inventory: ReleaseInventory, package: Package
) -> tuple[str | None, str | None, str]:
    record = next((t for t in inventory.tags if t[0].startswith(package.prefix)), None)
    if record is None:
        return None, None, "release"
    tag, commit = record
    parse_tag(tag.removeprefix(package.prefix))
    if not commit:
        raise ValueError(f"Release tag does not point to a commit: {tag}")
    if commit == inventory.ref:
        return tag, commit, "already_released"
    if not _changed(inventory, package, commit):
        return tag, commit, "unchanged"
    return tag, commit, "release"


def _entry(inventory: ReleaseInventory, package: Package) -> dict[str, object]:
    tag, tag_commit, action = _basis(inventory, package)
    base = f"{tag_commit}..{inventory.ref}" if tag_commit else inventory.ref
    subjects = []
    if action == "release":
        subjects = git_output(
            inventory.root, ["log", base, "--format=%s", "--", package.path]
        ).splitlines()
    bump, version, breaking = release_suggestion(subjects, tag)
    if action != "release" and tag:
        version = tag.removeprefix(package.prefix)
        bump = "none"
    names = {p.name for p in inventory.packages}
    dependencies = sorted(
        {canonicalize_name(Requirement(r).name) for r in package.required} & names
    )
    return {
        "name": package.name,
        "path": package.path,
        "private": package.private,
        "dependencies": dependencies,
        "requirements": list(package.required),
        "optional_requirements": list(package.optional),
        "current_tag": tag,
        "current_tag_commit": tag_commit,
        "suggested_bump": bump,
        "suggested_next": version,
        "breaking": breaking,
        "tag": f"{package.prefix}{version}",
        "action": action,
    }


def plan_releases(root: Path, ref: str = "HEAD") -> dict[str, object]:
    """Plan every actual member at a pinned revision without any Git mutation.

    Inventory/tag discovery runs once; manifests use one cat-file batch. Only
    changed packages query scoped history. Optional extras are reported intact
    rather than introducing plugin cycles into the mandatory order. Conditional
    mandatory requirements are conservatively included across target platforms.
    """
    inventory = read_inventory(root, ref)
    order = release_order(inventory.packages)
    by_name = {p.name: p for p in inventory.packages}
    entries = [_entry(inventory, by_name[name]) for name in order]
    return {
        "ref": inventory.ref,
        "order": order,
        "packages": entries,
        "excluded": list(inventory.excluded),
        "ready": True,
        "warnings": [
            "Optional requirements need index availability checks before publication.",
            "Only local tags are inspected; verify relevant remote tag identities.",
        ],
    }
