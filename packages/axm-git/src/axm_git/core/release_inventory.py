"""Read package metadata from one immutable Git tree without checking it out."""

from __future__ import annotations

import subprocess
import tomllib
from dataclasses import dataclass
from fnmatch import fnmatchcase
from functools import cache
from pathlib import Path, PurePosixPath

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from axm_git.core.runner import run_git

__all__ = ["Package", "ReleaseInventory", "git_output", "read_inventory"]

_BLOB_HEADER_FIELDS = 3


@dataclass(frozen=True)
class Package:
    """One real distribution, identified by its normalized project name."""

    name: str
    path: str
    prefix: str
    required: tuple[str, ...]
    optional: tuple[str, ...]
    private: bool


@dataclass(frozen=True)
class ReleaseInventory:
    """Metadata and tags captured once for a resolved commit."""

    root: Path
    ref: str
    packages: tuple[Package, ...]
    tags: tuple[tuple[str, str], ...]
    excluded: tuple[str, ...]


def git_output(root: Path, args: list[str]) -> str:
    """Read Git output, refusing errors instead of inventing empty evidence."""
    result = run_git(args, root)
    if result.returncode:
        raise ValueError(result.stderr.strip() or f"git {args[0]} failed")
    return result.stdout


def _table(value: object) -> dict[str, object]:
    """Validate a TOML table before accessing nested configuration."""
    if not isinstance(value, dict):
        raise ValueError("Expected a TOML table")
    return {str(key): item for key, item in value.items()}


def _strings(value: object) -> list[str]:
    """Validate a list of workspace patterns or build requirements."""
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError("Expected a list of strings")
    return [str(v) for v in value]


def _matches(path: str, pattern: str) -> bool:
    """Match anchored workspace globs, including recursive ** components."""
    parts = PurePosixPath(pattern).parts
    if not parts or PurePosixPath(pattern).is_absolute() or ".." in parts:
        raise ValueError(f"Workspace pattern escapes the repository: {pattern}")
    names = PurePosixPath(path).parts

    @cache
    def match(i: int, j: int) -> bool:
        if i == len(parts):
            return j == len(names)
        if parts[i] == "**":
            return match(i + 1, j) or (j < len(names) and match(i, j + 1))
        return (
            j < len(names) and fnmatchcase(names[j], parts[i]) and match(i + 1, j + 1)
        )

    return match(0, 0)


def _tag_records(root: Path) -> tuple[tuple[str, str], ...]:
    """Capture tag names and peeled immutable commit ids in one scan."""
    format_fields = (
        "%(refname:strip=2)%00%(objecttype)%00%(objectname)"
        "%00%(*objecttype)%00%(*objectname)"
    )
    text = git_output(
        root,
        [
            "for-each-ref",
            "--sort=-version:refname",
            f"--format={format_fields}",
            "refs/tags",
        ],
    )
    records = []
    for line in text.splitlines():
        name, kind, oid, peeled_kind, peeled = line.split("\0")
        commit = oid if kind == "commit" else peeled if peeled_kind == "commit" else ""
        records.append((name, commit))
    return tuple(records)


def _included(directory: str, members: list[str], excludes: list[str]) -> bool:
    """Apply workspace inclusion and exclusion rules to one directory."""
    return any(_matches(directory, pat) for pat in members) and not any(
        _matches(directory, pat) for pat in excludes
    )


def _member_files(config: dict[str, object], paths: list[str]) -> list[str]:
    """Expand workspace members/excludes against the pinned tree, not disk."""
    uv = _table(_table(config.get("tool", {})).get("uv", {}))
    if "workspace" not in uv:
        return ["pyproject.toml"]
    workspace = _table(uv["workspace"])
    members = _strings(workspace.get("members", []))
    excludes = _strings(workspace.get("exclude", []))
    directories = {
        str(parent)
        for path in paths
        for parent in PurePosixPath(path).parents
        if str(parent) != "."
    }
    selected = {
        directory
        for directory in directories
        if _included(directory, members, excludes)
    }
    result = ["pyproject.toml"]
    for directory in sorted(selected):
        file = f"{directory}/pyproject.toml"
        if file not in paths:
            raise ValueError(f"Workspace member has no pyproject.toml: {directory}")
        result.append(file)
    return result


def _read_blobs(root: Path, ref: str, files: list[str]) -> list[str]:
    """Read all selected manifests with one size-framed cat-file subprocess."""
    requests = "".join(f"{ref}:{file}\n" for file in files).encode()
    result = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=root,
        input=requests,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if result.returncode:
        raise ValueError(result.stderr.decode(errors="replace").strip())
    content = result.stdout
    offset = 0
    texts = []
    for file in files:
        end = content.index(b"\n", offset)
        header = content[offset:end].split()
        if len(header) != _BLOB_HEADER_FIELDS or header[1] != b"blob":
            raise ValueError(f"Not a regular metadata blob: {file}")
        size = int(header[2])
        offset = end + 1
        texts.append(content[offset : offset + size].decode("utf-8"))
        offset += size + 1
    return texts


def _requirements(
    project: dict[str, object], build: dict[str, object], file: str
) -> tuple[list[str], list[str]]:
    """Validate static required and optional PEP 508 requirements."""
    dynamic = _strings(project.get("dynamic", []))
    if {"name", "dependencies", "optional-dependencies"} & set(dynamic):
        raise ValueError(f"Dynamic release dependency metadata: {file}")
    required = _strings(project.get("dependencies", [])) + _strings(
        build.get("requires", [])
    )
    groups = _table(project.get("optional-dependencies", {}))
    optional = [r for group in groups.values() for r in _strings(group)]
    for requirement in required + optional:
        Requirement(requirement)
    return required, optional


def _package(file: str, text: str) -> Package | None:
    """Parse static package identity, release prefix and dependency contracts."""
    config: dict[str, object] = tomllib.loads(text)
    tool = _table(config.get("tool", {}))
    uv = _table(tool.get("uv", {}))
    if "build-system" not in config or uv.get("package") is False:
        return None
    project = _table(config.get("project", {}))
    name = project.get("name")
    if not isinstance(name, str):
        raise ValueError(f"Missing project name: {file}")
    required, optional = _requirements(project, _table(config["build-system"]), file)
    version = _table(_table(tool.get("hatch", {})).get("version", {}))
    pattern = version.get("tag-pattern")
    suffix = "(?P<version>.*)"
    if not isinstance(pattern, str) or not pattern.endswith(suffix):
        raise ValueError(f"Missing supported hatch-vcs tag-pattern: {file}")
    prefix = pattern.removesuffix(suffix)
    if not prefix.endswith("v"):
        raise ValueError(f"Unsupported version tag prefix: {file}")
    return Package(
        name=canonicalize_name(name, validate=True),
        path=str(PurePosixPath(file).parent),
        prefix=prefix,
        required=tuple(required),
        optional=tuple(optional),
        private="Private :: Do Not Upload" in _strings(project.get("classifiers", [])),
    )


def _validate_unique(packages: list[Package]) -> None:
    """Refuse ambiguous project identities and release namespaces."""
    for attribute in ("name", "prefix"):
        values = [getattr(package, attribute) for package in packages]
        if len(set(values)) != len(values):
            raise ValueError(f"Duplicate release package {attribute}")


def read_inventory(root: Path, ref: str) -> ReleaseInventory:
    """Capture the immutable manifest inventory and local tags exactly once."""
    commit = git_output(
        root, ["rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"]
    ).strip()
    config: dict[str, object] = tomllib.loads(
        git_output(root, ["show", f"{commit}:pyproject.toml"])
    )
    paths = git_output(root, ["ls-tree", "-r", "--name-only", "-z", commit]).split("\0")
    files = _member_files(config, paths)
    packages = []
    excluded = []
    for file, text in zip(files, _read_blobs(root, commit, files), strict=True):
        package = _package(file, text)
        if package is None:
            excluded.append(file)
        else:
            packages.append(package)
    _validate_unique(packages)
    if not packages:
        raise ValueError("No release packages in the selected tree")
    tags = _tag_records(root)
    return ReleaseInventory(root, commit, tuple(packages), tuple(tags), tuple(excluded))
