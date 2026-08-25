"""Node monorepo (workspace) gold-standard checks.

Ports the intent of the Python ``checks.workspace`` (uv workspace) to the node
ecosystem: npm/pnpm/yarn workspaces. These checks only fire when the project is
actually a workspace root (a ``workspaces`` field or ``pnpm-workspace.yaml``);
on a single-package project they pass as not-applicable, mirroring how the
Python workspace checks skip outside a workspace context.
"""

from __future__ import annotations

import json
from pathlib import Path

from axm_init.models.check import CheckResult

__all__ = [
    "check_packages_layout",
    "check_workspaces_declared",
    "check_workspaces_versions_consistent",
]


def _load_package_json(project: Path) -> dict[str, object] | None:
    """Load and parse the root ``package.json``; ``None`` if absent/invalid."""
    path = project / "package.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _is_workspace_root(project: Path) -> bool:
    """Return True if *project* is an npm/pnpm/yarn workspace root."""
    if (project / "pnpm-workspace.yaml").is_file():
        return True
    data = _load_package_json(project)
    return data is not None and "workspaces" in data


def _ok(name: str, weight: int, message: str) -> CheckResult:
    """Build a passing workspace check result."""
    return CheckResult(
        name=name,
        category="workspace",
        passed=True,
        weight=weight,
        message=message,
        details=[],
        fix="",
    )


def check_workspaces_declared(project: Path) -> CheckResult:
    """Check: a workspace root declares its members (workspaces / pnpm-workspace).

    Not applicable (auto-pass) on a single-package project.
    """
    if not _is_workspace_root(project):
        return _ok("workspace.workspaces_declared", 3, "Not a workspace (n/a)")
    return _ok("workspace.workspaces_declared", 3, "Workspace members declared")


def check_packages_layout(project: Path) -> CheckResult:
    """Check: a workspace root has a ``packages/`` directory with members."""
    if not _is_workspace_root(project):
        return _ok("workspace.packages_layout", 2, "Not a workspace (n/a)")
    packages = project / "packages"
    if packages.is_dir() and any(
        (child / "package.json").is_file()
        for child in packages.iterdir()
        if child.is_dir()
    ):
        return _ok("workspace.packages_layout", 2, "packages/* layout present")
    return CheckResult(
        name="workspace.packages_layout",
        category="workspace",
        passed=False,
        weight=2,
        message="No packages/* members found",
        details=["A workspace root should hold its members under packages/"],
        fix="Place workspace members under packages/<name>/ with a package.json.",
    )


def _member_dirs(project: Path) -> list[Path]:
    """Return the member directories that have a package.json under packages/."""
    packages = project / "packages"
    if not packages.is_dir():
        return []
    return [
        child
        for child in sorted(packages.iterdir())
        if child.is_dir() and (child / "package.json").is_file()
    ]


def check_workspaces_versions_consistent(project: Path) -> CheckResult:
    """Check: every workspace member declares a version (release readiness).

    Not applicable (auto-pass) outside a workspace. Flags members whose
    ``package.json`` omits ``version`` — the node analog of the Python
    ``requires_python_compat`` cross-member consistency check.
    """
    if not _is_workspace_root(project):
        return _ok("workspace.versions_consistent", 2, "Not a workspace (n/a)")
    missing: list[str] = []
    for member in _member_dirs(project):
        try:
            data = json.loads((member / "package.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if not (isinstance(data, dict) and data.get("version")):
            missing.append(member.name)
    if missing:
        return CheckResult(
            name="workspace.versions_consistent",
            category="workspace",
            passed=False,
            weight=2,
            message=f"{len(missing)} member(s) without a version",
            details=[f"Missing version: {', '.join(missing)}"],
            fix="Add a `version` field to each member's package.json.",
        )
    return _ok("workspace.versions_consistent", 2, "All members versioned")
