"""Node structure gold-standard checks — license, contributing, readme, gitignore.

Ports the intent of the Python ``checks.structure`` / ``checks.docs.readme``
gold-standard files to a node project. These are language-agnostic project
hygiene files; the README section convention matches the Python check.
"""

from __future__ import annotations

from pathlib import Path

from axm_init.models.check import CheckResult

__all__ = [
    "check_contributing",
    "check_gitignore",
    "check_license_file",
    "check_readme",
]

_README_SECTIONS = ("Features", "Installation", "Development", "License")


def check_license_file(project: Path) -> CheckResult:
    """Check: a LICENSE file exists at the project root."""
    if (project / "LICENSE").is_file() or (project / "LICENSE.md").is_file():
        return CheckResult(
            name="structure.license",
            category="structure",
            passed=True,
            weight=3,
            message="LICENSE file found",
            details=[],
            fix="",
        )
    return CheckResult(
        name="structure.license",
        category="structure",
        passed=False,
        weight=3,
        message="LICENSE file not found",
        details=[],
        fix="Create a LICENSE file (MIT, Apache-2.0, …).",
    )


def check_contributing(project: Path) -> CheckResult:
    """Check: a CONTRIBUTING.md exists at the project root."""
    if (project / "CONTRIBUTING.md").is_file():
        return CheckResult(
            name="structure.contributing",
            category="structure",
            passed=True,
            weight=2,
            message="CONTRIBUTING.md found",
            details=[],
            fix="",
        )
    return CheckResult(
        name="structure.contributing",
        category="structure",
        passed=False,
        weight=2,
        message="CONTRIBUTING.md not found",
        details=[],
        fix="Create CONTRIBUTING.md with dev setup and commit conventions.",
    )


def check_gitignore(project: Path) -> CheckResult:
    """Check: a .gitignore exists that ignores node_modules."""
    path = project / ".gitignore"
    if not path.is_file():
        return CheckResult(
            name="structure.gitignore",
            category="structure",
            passed=False,
            weight=2,
            message=".gitignore not found",
            details=[],
            fix="Create a .gitignore ignoring node_modules, dist, coverage.",
        )
    content = path.read_text(encoding="utf-8", errors="replace")
    if "node_modules" not in content:
        return CheckResult(
            name="structure.gitignore",
            category="structure",
            passed=False,
            weight=2,
            message=".gitignore does not ignore node_modules",
            details=["node_modules must be git-ignored"],
            fix="Add node_modules/ to .gitignore.",
        )
    return CheckResult(
        name="structure.gitignore",
        category="structure",
        passed=True,
        weight=2,
        message=".gitignore present",
        details=[],
        fix="",
    )


def check_readme(project: Path) -> CheckResult:
    """Check: README.md exists with the standard sections."""
    path = project / "README.md"
    if not path.is_file():
        return CheckResult(
            name="structure.readme",
            category="structure",
            passed=False,
            weight=3,
            message="README.md not found",
            details=[],
            fix="Create README.md with Features/Installation/Development/License.",
        )
    lowered = path.read_text(encoding="utf-8", errors="replace").lower()
    missing = [s for s in _README_SECTIONS if f"## {s.lower()}" not in lowered]
    if missing:
        return CheckResult(
            name="structure.readme",
            category="structure",
            passed=False,
            weight=3,
            message=f"README missing {len(missing)} section(s)",
            details=[f"Missing: {', '.join(missing)}"],
            fix=f"Add {', '.join(missing)} section(s) to README.md.",
        )
    return CheckResult(
        name="structure.readme",
        category="structure",
        passed=True,
        weight=3,
        message="README follows standard",
        details=[],
        fix="",
    )
