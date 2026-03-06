"""Workspace-specific checks — only relevant for workspace roots."""

from __future__ import annotations

import logging
from pathlib import Path

from axm_init.checks._utils import _load_toml
from axm_init.models.check import CheckResult

logger = logging.getLogger(__name__)

__all__ = [
    "check_matrix_packages",
    "check_members_consistent",
    "check_monorepo_plugin",
    "check_packages_layout",
    "check_requires_python_compat",
]


def _resolve_member_dirs(project: Path) -> list[Path]:
    """Return resolved member directories from workspace config."""
    data = _load_toml(project)
    if data is None:
        return []

    ws_config = data.get("tool", {}).get("uv", {}).get("workspace", {})
    member_globs = ws_config.get("members", [])
    if not member_globs:
        return []

    dirs: list[Path] = []
    for pattern in member_globs:
        for candidate in project.glob(pattern):
            if candidate.is_dir() and (candidate / "pyproject.toml").exists():
                dirs.append(candidate)

    return sorted(dirs, key=lambda p: p.name)


def check_packages_layout(project: Path) -> CheckResult:
    """Check that workspace members live under a packages/ subdir."""
    member_dirs = _resolve_member_dirs(project)
    if not member_dirs:
        return CheckResult(
            name="workspace.packages_layout",
            category="workspace",
            passed=True,
            weight=3,
            message="No members yet (workspace configured)",
            details=[],
            fix="",
        )

    bad = [d.name for d in member_dirs if "packages" not in d.parts]
    if bad:
        return CheckResult(
            name="workspace.packages_layout",
            category="workspace",
            passed=False,
            weight=3,
            message=f"{len(bad)} member(s) outside packages/",
            details=[f"Outside packages/: {', '.join(bad)}"],
            fix="Move workspace members under packages/ subdirectory.",
        )

    return CheckResult(
        name="workspace.packages_layout",
        category="workspace",
        passed=True,
        weight=3,
        message=f"{len(member_dirs)} member(s) in packages/",
        details=[],
        fix="",
    )


def check_members_consistent(project: Path) -> CheckResult:
    """Check each member has pyproject.toml, src/, and tests/."""
    member_dirs = _resolve_member_dirs(project)
    if not member_dirs:
        return CheckResult(
            name="workspace.members_consistent",
            category="workspace",
            passed=True,
            weight=2,
            message="No members yet (workspace configured)",
            details=[],
            fix="",
        )

    issues: list[str] = []
    for member in member_dirs:
        missing: list[str] = []
        if not (member / "pyproject.toml").exists():
            missing.append("pyproject.toml")
        if not (member / "src").is_dir():
            missing.append("src/")
        if not (member / "tests").is_dir():
            missing.append("tests/")
        if missing:
            issues.append(f"{member.name}: missing {', '.join(missing)}")

    if issues:
        return CheckResult(
            name="workspace.members_consistent",
            category="workspace",
            passed=False,
            weight=2,
            message=f"{len(issues)} inconsistent member(s)",
            details=issues,
            fix="Ensure each member has pyproject.toml, src/, and tests/.",
        )

    return CheckResult(
        name="workspace.members_consistent",
        category="workspace",
        passed=True,
        weight=2,
        message=f"{len(member_dirs)} member(s) consistent",
        details=[],
        fix="",
    )


def check_monorepo_plugin(project: Path) -> CheckResult:
    """Check root mkdocs.yml uses the monorepo plugin."""
    mkdocs_path = project / "mkdocs.yml"
    if not mkdocs_path.exists():
        return CheckResult(
            name="workspace.monorepo_plugin",
            category="workspace",
            passed=False,
            weight=2,
            message="mkdocs.yml not found at workspace root",
            details=["Workspace docs need mkdocs-monorepo-plugin"],
            fix="Create mkdocs.yml with monorepo plugin.",
        )

    content = mkdocs_path.read_text()
    if "monorepo" not in content:
        return CheckResult(
            name="workspace.monorepo_plugin",
            category="workspace",
            passed=False,
            weight=2,
            message="monorepo plugin not configured",
            details=["mkdocs.yml exists but missing monorepo plugin"],
            fix="Add 'monorepo' to plugins list in mkdocs.yml.",
        )

    return CheckResult(
        name="workspace.monorepo_plugin",
        category="workspace",
        passed=True,
        weight=2,
        message="monorepo plugin configured",
        details=[],
        fix="",
    )


def check_matrix_packages(project: Path) -> CheckResult:
    """Check CI workflow uses --package for per-member testing."""
    ci_path = project / ".github" / "workflows" / "ci.yml"
    if not ci_path.exists():
        return CheckResult(
            name="workspace.matrix_packages",
            category="workspace",
            passed=False,
            weight=2,
            message="CI workflow not found",
            details=["Expected .github/workflows/ci.yml"],
            fix="Create CI workflow with per-package test matrix.",
        )

    content = ci_path.read_text()
    if "--package" not in content:
        return CheckResult(
            name="workspace.matrix_packages",
            category="workspace",
            passed=False,
            weight=2,
            message="No --package strategy in CI",
            details=["CI should use --package for per-member testing"],
            fix="Add --package flag to test/lint jobs in CI matrix.",
        )

    return CheckResult(
        name="workspace.matrix_packages",
        category="workspace",
        passed=True,
        weight=2,
        message="CI uses --package strategy",
        details=[],
        fix="",
    )


def check_requires_python_compat(project: Path) -> CheckResult:
    """Check requires-python compatibility across members."""
    member_dirs = _resolve_member_dirs(project)
    if not member_dirs:
        return CheckResult(
            name="workspace.requires_python_compat",
            category="workspace",
            passed=True,
            weight=1,
            message="No members to check",
            details=[],
            fix="",
        )

    specs: dict[str, str] = {}
    for member in member_dirs:
        data = _load_toml(member)
        if data is None:
            continue
        req = data.get("project", {}).get("requires-python")
        if isinstance(req, str):
            specs[member.name] = req

    if not specs:
        return CheckResult(
            name="workspace.requires_python_compat",
            category="workspace",
            passed=True,
            weight=1,
            message="No requires-python found in members",
            details=[],
            fix="",
        )

    unique = set(specs.values())
    if len(unique) == 1:
        return CheckResult(
            name="workspace.requires_python_compat",
            category="workspace",
            passed=True,
            weight=1,
            message=f"All members: {next(iter(unique))}",
            details=[],
            fix="",
        )

    detail_lines = [f"  {name}: {spec}" for name, spec in sorted(specs.items())]
    return CheckResult(
        name="workspace.requires_python_compat",
        category="workspace",
        passed=False,
        weight=1,
        message=f"{len(unique)} different requires-python values",
        details=detail_lines,
        fix="Align requires-python across workspace members.",
    )
