"""Workspace-specific checks — only relevant for workspace roots."""

from __future__ import annotations

import logging
from fnmatch import fnmatchcase
from pathlib import Path

from axm_ingot.suite import resolve_suite_dir

from axm_init.checks._utils import TomlTable, load_toml, section
from axm_init.models.check import CheckResult

logger = logging.getLogger(__name__)

__all__ = [
    "check_matrix_packages",
    "check_members_consistent",
    "check_monorepo_plugin",
    "check_packages_layout",
    "check_pytest_importmode",
    "check_pytest_testpaths",
    "check_quality_workflow",
    "check_requires_python_compat",
    "check_root_name_collision",
]


def _resolve_member_dirs(project: Path) -> list[Path]:
    """Return resolved member directories from workspace config."""
    data = load_toml(project)
    if data is None:
        return []

    ws_config = section(section(section(data, "tool"), "uv"), "workspace")
    member_globs_raw = ws_config.get("members", [])
    if not isinstance(member_globs_raw, list) or not member_globs_raw:
        return []

    dirs: list[Path] = []
    for pattern in member_globs_raw:
        if not isinstance(pattern, str):
            continue
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
        data = load_toml(member)
        if data is None:
            continue
        req = section(data, "project").get("requires-python")
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


# ── New checks (AXM-313) ────────────────────────────────────────────────────


def _get_member_names(project: Path) -> list[str]:
    """Return project names of all workspace members."""
    names: list[str] = []
    for member_dir in _resolve_member_dirs(project):
        data = load_toml(member_dir)
        if data is not None:
            name = section(data, "project").get("name")
            if isinstance(name, str):
                names.append(name)
    return names


def check_root_name_collision(project: Path) -> CheckResult:
    """Check that root project name does not collide with any member name."""
    data = load_toml(project)
    if data is None:
        return CheckResult(
            name="workspace.root_name_collision",
            category="workspace",
            passed=True,
            weight=3,
            message="No pyproject.toml at root",
            details=[],
            fix="",
        )

    root_name_raw = section(data, "project").get("name", "")
    root_name = root_name_raw if isinstance(root_name_raw, str) else ""
    member_names = _get_member_names(project)
    if not member_names:
        return CheckResult(
            name="workspace.root_name_collision",
            category="workspace",
            passed=True,
            weight=3,
            message="No members yet",
            details=[],
            fix="",
        )

    collisions = [m for m in member_names if m.casefold() == root_name.casefold()]
    if collisions:
        return CheckResult(
            name="workspace.root_name_collision",
            category="workspace",
            passed=False,
            weight=3,
            message=f"Root name '{root_name}' collides with member(s)",
            details=[
                f"Collision: root='{root_name}', member='{c}'" for c in collisions
            ],
            fix="Rename root project or member to avoid name collision.",
        )

    return CheckResult(
        name="workspace.root_name_collision",
        category="workspace",
        passed=True,
        weight=3,
        message=(
            f"Root '{root_name}' does not collide with {len(member_names)} member(s)"
        ),
        details=[],
        fix="",
    )


def _get_pytest_config(data: TomlTable) -> TomlTable:
    """Extract [tool.pytest.ini_options] section."""
    return section(section(section(data, "tool"), "pytest"), "ini_options")


def check_pytest_importmode(project: Path) -> CheckResult:
    """Check root pytest has import_mode = 'importlib'."""
    data = load_toml(project)
    if data is None:
        return CheckResult(
            name="workspace.pytest_importmode",
            category="workspace",
            passed=False,
            weight=2,
            message="No pyproject.toml at root",
            details=[],
            fix="Create pyproject.toml with [tool.pytest.ini_options].",
        )

    pytest_cfg = _get_pytest_config(data)
    import_mode = pytest_cfg.get("import_mode", pytest_cfg.get("importmode", ""))

    if import_mode == "importlib":
        return CheckResult(
            name="workspace.pytest_importmode",
            category="workspace",
            passed=True,
            weight=2,
            message="import_mode = 'importlib' set",
            details=[],
            fix="",
        )

    return CheckResult(
        name="workspace.pytest_importmode",
        category="workspace",
        passed=False,
        weight=2,
        message="import_mode not set to 'importlib'",
        details=[f"Current value: '{import_mode}'" if import_mode else "Key missing"],
        fix='Add import_mode = "importlib" to [tool.pytest.ini_options].',
    )


def _testpath_covers_suite(testpath: str, suite_path: str) -> bool:
    """Return whether one configured testpath includes a member suite."""
    normalized = testpath.strip().replace("\\", "/").rstrip("/")
    if not normalized:
        return False
    return (
        fnmatchcase(suite_path, normalized)
        or suite_path == normalized
        or suite_path.startswith(f"{normalized}/")
    )


def _resolved_member_suites(project: Path) -> list[tuple[Path, Path]]:
    """Resolve only workspace members that currently own a test suite."""
    suites: list[tuple[Path, Path]] = []
    for member in _resolve_member_dirs(project):
        suite = resolve_suite_dir(member)
        if suite is not None:
            suites.append((member, suite))
    return suites


def check_pytest_testpaths(project: Path) -> CheckResult:
    """Check root testpaths covers every existing workspace member suite."""
    data = load_toml(project)
    if data is None:
        return CheckResult(
            name="workspace.pytest_testpaths",
            category="workspace",
            passed=False,
            weight=2,
            message="No pyproject.toml at root",
            details=[],
            fix="Create pyproject.toml with [tool.pytest.ini_options].",
        )

    pytest_cfg = _get_pytest_config(data)
    testpaths_raw = pytest_cfg.get("testpaths", [])
    testpaths: list[str] = (
        [path for path in testpaths_raw if isinstance(path, str)]
        if isinstance(testpaths_raw, list)
        else []
    )
    if not testpaths:
        return CheckResult(
            name="workspace.pytest_testpaths",
            category="workspace",
            passed=False,
            weight=2,
            message="No testpaths configured",
            details=["Expected testpaths listing member test directories"],
            fix=(
                "Add every existing member suite to "
                "[tool.pytest.ini_options].testpaths."
            ),
        )

    member_suites = _resolved_member_suites(project)
    uncovered: list[tuple[Path, str]] = []
    for member, suite in member_suites:
        suite_path = suite.relative_to(project).as_posix()
        if not any(
            _testpath_covers_suite(testpath, suite_path) for testpath in testpaths
        ):
            uncovered.append((member, suite_path))

    if uncovered:
        details = [f"{member.name}: {suite_path}" for member, suite_path in uncovered]
        missing_paths = [suite_path for _, suite_path in uncovered]
        return CheckResult(
            name="workspace.pytest_testpaths",
            category="workspace",
            passed=False,
            weight=2,
            message=(f"testpaths does not cover {len(uncovered)} member suite(s)"),
            details=details,
            fix=(f"Add the uncovered suites to testpaths: {', '.join(missing_paths)}"),
        )

    return CheckResult(
        name="workspace.pytest_testpaths",
        category="workspace",
        passed=True,
        weight=2,
        message=f"testpaths cover {len(member_suites)} member suite(s)",
        details=[],
        fix="",
    )


def check_suite_dir_uniqueness(project: Path) -> CheckResult:
    """Check every workspace member suite directory name is unique."""
    owners: dict[str, list[str]] = {}
    for member, suite in _resolved_member_suites(project):
        owners.setdefault(suite.name, []).append(member.name)

    duplicates = {
        suite_name: sorted(member_names)
        for suite_name, member_names in owners.items()
        if len(member_names) > 1
    }
    if duplicates:
        details = [
            f"{suite_name}: {', '.join(member_names)}"
            for suite_name, member_names in sorted(duplicates.items())
        ]
        names = ", ".join(sorted(duplicates))
        return CheckResult(
            name="workspace.suite_dir_uniqueness",
            category="workspace",
            passed=False,
            weight=2,
            message=f"Duplicate suite directory names: {names}",
            details=details,
            fix=(
                "Rename each duplicate suite to its canonical "
                "tests_<normalized-package> name."
            ),
        )

    return CheckResult(
        name="workspace.suite_dir_uniqueness",
        category="workspace",
        passed=True,
        weight=2,
        message=f"{len(owners)} member suite name(s) are unique",
        details=[],
        fix="",
    )


def check_quality_workflow(project: Path) -> CheckResult:
    """Check .github/workflows/axm-quality.yml exists with per-package audit."""
    quality_path = project / ".github" / "workflows" / "axm-quality.yml"
    if not quality_path.exists():
        return CheckResult(
            name="workspace.quality_workflow",
            category="workspace",
            passed=False,
            weight=2,
            message="axm-quality.yml not found",
            details=["Expected .github/workflows/axm-quality.yml"],
            fix="Create axm-quality.yml with per-package audit + coverage.",
        )

    content = quality_path.read_text()
    # Verify it has per-package audit and coverage
    has_audit = "axm-audit" in content or "audit" in content.lower()
    has_coverage = "coverage" in content.lower()

    if has_audit and has_coverage:
        return CheckResult(
            name="workspace.quality_workflow",
            category="workspace",
            passed=True,
            weight=2,
            message="axm-quality.yml configured with audit + coverage",
            details=[],
            fix="",
        )

    missing = []
    if not has_audit:
        missing.append("audit")
    if not has_coverage:
        missing.append("coverage")

    return CheckResult(
        name="workspace.quality_workflow",
        category="workspace",
        passed=False,
        weight=2,
        message=f"axm-quality.yml missing: {', '.join(missing)}",
        details=[f"Workflow exists but missing: {', '.join(missing)}"],
        fix="Add per-package audit + coverage to axm-quality.yml.",
    )
