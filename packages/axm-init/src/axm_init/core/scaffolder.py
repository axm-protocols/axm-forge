"""Shared scaffolding seam.

Single source of truth for the pieces that the AXMTool layer
(:mod:`axm_init.tools.scaffold`) needs when scaffolding a workspace *member*:
the copier template-variable build, workspace-root resolution, and
workspace-name read. The generic AXM CLI and MCP surfaces both derive from
that tool instead of keeping private copies of this logic.
"""

from __future__ import annotations

import re
import tomllib
import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, Unpack

__all__ = [
    "WorkspaceIdentity",
    "build_member_data",
    "read_workspace_identity",
    "read_workspace_name",
    "resolve_workspace_root",
]

_DEFAULT_MEMBER_DESCRIPTION = "A workspace member package"
_GITHUB_REPOSITORY = re.compile(
    r"^https?://github\.com/(?P<slug>[^/\s]+/[^/\s]+?)(?:\.git)?/?$"
)
_MKDOCS_LINK_KEYS = frozenset({"repo_url", "site_url"})


@dataclass(frozen=True, slots=True)
class WorkspaceIdentity:
    """A workspace's name, and where its repository and documentation live.

    Attributes:
        name: Root ``[project].name`` (or the checkout directory name).
        repository: GitHub ``owner/name`` of the workspace repository.
        site_url: Root URL of the workspace documentation site, without a
            trailing slash; each member is published under ``<site_url>/<name>/``.
    """

    name: str
    repository: str
    site_url: str

    @classmethod
    def on_github(cls, name: str, repository: str) -> WorkspaceIdentity:
        """Identity of a repository documented on its GitHub Pages site."""
        owner, _, repo = repository.partition("/")
        return cls(name, repository, f"https://{owner}.github.io/{repo}")


class _LegacyMemberKeywords(TypedDict, total=False):
    """Keywords of the former :func:`build_member_data` signature."""

    workspace_name: str


def _workspace_argument(
    workspace: str | WorkspaceIdentity | None, legacy: Mapping[str, object]
) -> str | WorkspaceIdentity:
    """Resolve the ``workspace`` argument, honouring the deprecated keyword."""
    unknown = sorted(set(legacy) - _LegacyMemberKeywords.__optional_keys__)
    if unknown:
        msg = f"build_member_data() got an unexpected keyword argument {unknown[0]!r}"
        raise TypeError(msg)
    legacy_name = legacy.get("workspace_name")
    if legacy_name is None:
        if workspace is None:
            msg = "build_member_data() missing required argument: 'workspace'"
            raise TypeError(msg)
        return workspace
    if workspace is not None:
        msg = "build_member_data() got both 'workspace' and 'workspace_name'"
        raise TypeError(msg)
    warnings.warn(
        "build_member_data(workspace_name=...) is deprecated; "
        "pass workspace=... instead",
        DeprecationWarning,
        stacklevel=3,
    )
    return str(legacy_name)


def build_member_data(
    member_name: str,
    workspace: str | WorkspaceIdentity | None = None,
    scaffold_data: Mapping[str, str] | None = None,
    *,
    license_holder: str | None = None,
    private: bool | None = None,
    **legacy: Unpack[_LegacyMemberKeywords],
) -> dict[str, object]:
    """Build copier template variables for a workspace member scaffold.

    Args:
        member_name: Name of the new member package.
        workspace: Parent workspace, as resolved by
            :func:`read_workspace_identity`; a bare name stands for
            ``org/<name>`` documented on GitHub Pages. Required.
        scaffold_data: Caller identity fields — ``org``, ``author_name``,
            ``author_email``, ``license`` and optionally ``description``.
            Required.
        license_holder: Explicit LICENSE holder; falls back to ``org``.
        private: Publication guard forwarded to Copier when provided.
        **legacy: ``workspace_name``, the deprecated spelling of *workspace*
            (a bare name) kept for callers written against the former
            signature; it emits a :class:`DeprecationWarning`.

    Returns:
        The template-variable dict passed verbatim to copier. Identical inputs
        yield a byte-identical dict whatever the calling interface.

    Raises:
        TypeError: If *scaffold_data* or the workspace is missing, if both
            *workspace* and ``workspace_name`` are given, or on an unknown
            keyword.
    """
    if scaffold_data is None:
        msg = "build_member_data() missing required argument: 'scaffold_data'"
        raise TypeError(msg)
    org = scaffold_data["org"]
    workspace = _workspace_argument(workspace, legacy)
    if isinstance(workspace, str):
        workspace = WorkspaceIdentity.on_github(workspace, f"{org}/{workspace}")
    data: dict[str, object] = {
        "member_name": member_name,
        "workspace_name": workspace.name,
        "description": scaffold_data.get("description") or _DEFAULT_MEMBER_DESCRIPTION,
        "org": org,
        "license": scaffold_data["license"],
        "license_holder": license_holder or org,
        "author_name": scaffold_data["author_name"],
        "author_email": scaffold_data["author_email"],
        "repository": workspace.repository,
        "docs_url": f"{workspace.site_url}/{member_name}/",
    }
    if private is not None:
        data["private"] = private
    return data


def resolve_workspace_root(target_path: Path) -> Path | None:
    """Resolve the workspace root for *target_path*, or ``None``.

    Returns *target_path* itself when it is a workspace root, the parent
    workspace root when *target_path* is a member, and ``None`` otherwise.
    """
    from axm_init.checks._workspace import (
        ProjectContext,
        detect_context,
        find_workspace_root,
    )

    context = detect_context(target_path)
    if context == ProjectContext.WORKSPACE:
        return target_path
    if context == ProjectContext.MEMBER:
        return find_workspace_root(target_path)
    return None


def _github_repository(url: object) -> str | None:
    if not isinstance(url, str):
        return None
    match = _GITHUB_REPOSITORY.match(url.strip())
    return match.group("slug") if match else None


def _mkdocs_links(mkdocs: Path) -> dict[str, str]:
    """Read top-level ``repo_url`` / ``site_url`` scalars from ``mkdocs.yml``.

    Read line by line: mkdocs files carry custom tags (``!include``,
    ``!!python/name``) that a safe YAML loader refuses.
    """
    if not mkdocs.is_file():
        return {}
    links: dict[str, str] = {}
    for line in mkdocs.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition(":")
        if sep and key in _MKDOCS_LINK_KEYS and value.strip():
            links[key] = value.split(" #")[0].strip().strip("'\"")
    return links


def _project_urls(pyproject: Path) -> dict[str, object]:
    if not pyproject.is_file():
        return {}
    with open(pyproject, "rb") as f:
        urls = tomllib.load(f).get("project", {}).get("urls", {})
    return urls if isinstance(urls, dict) else {}


def read_workspace_identity(workspace_root: Path, org: str) -> WorkspaceIdentity:
    """Resolve a workspace's name, repository and documentation site.

    The root ``mkdocs.yml`` (``repo_url``, ``site_url``) wins, since it is what
    the published site uses; then the root ``[project.urls]`` (``Repository``
    or ``Homepage``, ``Documentation``); then ``org/<checkout directory>`` on
    GitHub Pages. The root ``[project].name`` is never used: workspaces often
    name their root project ``<repository>-workspace``.
    """
    mkdocs = _mkdocs_links(workspace_root / "mkdocs.yml")
    urls = _project_urls(workspace_root / "pyproject.toml")
    repository = (
        _github_repository(mkdocs.get("repo_url"))
        or _github_repository(urls.get("Repository"))
        or _github_repository(urls.get("Homepage"))
        or f"{org}/{workspace_root.name}"
    )
    documentation = urls.get("Documentation")
    site_url = mkdocs.get("site_url") or (
        documentation if isinstance(documentation, str) else None
    )
    name = read_workspace_name(workspace_root)
    if not site_url:
        return WorkspaceIdentity.on_github(name, repository)
    return WorkspaceIdentity(name, repository, site_url.rstrip("/"))


def read_workspace_name(workspace_root: Path) -> str:
    """Read the workspace name from ``pyproject.toml`` or fall back to dir name."""
    root_pyproject = workspace_root / "pyproject.toml"
    if root_pyproject.is_file():
        with open(root_pyproject, "rb") as f:
            root_data = tomllib.load(f)
        return str(root_data.get("project", {}).get("name", workspace_root.name))
    return workspace_root.name
