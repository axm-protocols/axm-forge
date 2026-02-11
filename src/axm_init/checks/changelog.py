"""Audit checks for changelog (2 checks, 5 pts)."""

from __future__ import annotations

from pathlib import Path

from axm_init.models.audit import CheckResult

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


def check_gitcliff_config(project: Path) -> CheckResult:
    """Check 31: [tool.git-cliff] section in pyproject.toml."""
    path = project / "pyproject.toml"
    if not path.exists():
        return CheckResult(
            name="changelog.gitcliff",
            category="changelog",
            passed=False,
            weight=3,
            message="pyproject.toml not found",
            details=[],
            fix="Create pyproject.toml with [tool.git-cliff] section.",
        )
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except Exception:
        return CheckResult(
            name="changelog.gitcliff",
            category="changelog",
            passed=False,
            weight=3,
            message="pyproject.toml unparsable",
            details=[],
            fix="Fix TOML syntax and add [tool.git-cliff] section.",
        )
    if "git-cliff" not in data.get("tool", {}):
        return CheckResult(
            name="changelog.gitcliff",
            category="changelog",
            passed=False,
            weight=3,
            message="No [tool.git-cliff] config found",
            details=["git-cliff auto-generates CHANGELOG from conventional commits"],
            fix=(
                "Add [tool.git-cliff.changelog] and"
                " [tool.git-cliff.git] to pyproject.toml."
            ),
        )
    return CheckResult(
        name="changelog.gitcliff",
        category="changelog",
        passed=True,
        weight=3,
        message="git-cliff configured",
        details=[],
        fix="",
    )


def check_no_manual_changelog(project: Path) -> CheckResult:
    """Check 32: no manual CHANGELOG.md (git-cliff auto-generates)."""
    if (project / "CHANGELOG.md").exists():
        return CheckResult(
            name="changelog.no_manual",
            category="changelog",
            passed=False,
            weight=2,
            message="Manual CHANGELOG.md found",
            details=["git-cliff should auto-generate the changelog"],
            fix=(
                "Delete CHANGELOG.md - git-cliff generates"
                " it from conventional commits."
            ),
        )
    return CheckResult(
        name="changelog.no_manual",
        category="changelog",
        passed=True,
        weight=2,
        message="No manual CHANGELOG.md",
        details=[],
        fix="",
    )
