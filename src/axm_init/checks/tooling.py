"""Audit checks for developer tooling (6 checks, 14 pts)."""

from __future__ import annotations

from pathlib import Path

from axm_init.models.check import CheckResult


def _read_precommit(project: Path) -> str | None:
    """Read .pre-commit-config.yaml, or None if missing."""
    path = project / ".pre-commit-config.yaml"
    if not path.exists():
        return None
    return path.read_text()


def check_precommit_exists(project: Path) -> CheckResult:
    """Check 13: .pre-commit-config.yaml exists."""
    content = _read_precommit(project)
    if content is None:
        return CheckResult(
            name="tooling.precommit_exists",
            category="tooling",
            passed=False,
            weight=3,
            message=".pre-commit-config.yaml not found",
            details=[],
            fix=(
                "Create .pre-commit-config.yaml with"
                " ruff, mypy, and conventional-commit hooks."
            ),
        )
    return CheckResult(
        name="tooling.precommit_exists",
        category="tooling",
        passed=True,
        weight=3,
        message=".pre-commit-config.yaml found",
        details=[],
        fix="",
    )


def check_precommit_ruff(project: Path) -> CheckResult:
    """Check 14: ruff hook present."""
    content = _read_precommit(project)
    if content is None or "ruff" not in content:
        return CheckResult(
            name="tooling.precommit_ruff",
            category="tooling",
            passed=False,
            weight=2,
            message="No ruff hook in pre-commit",
            details=["ruff-pre-commit hook should be configured"],
            fix="Add ruff-pre-commit repo with ruff and ruff-format hooks.",
        )
    return CheckResult(
        name="tooling.precommit_ruff",
        category="tooling",
        passed=True,
        weight=2,
        message="Ruff hook present",
        details=[],
        fix="",
    )


def check_precommit_mypy(project: Path) -> CheckResult:
    """Check 15: mypy hook present."""
    content = _read_precommit(project)
    if content is None or "mypy" not in content:
        return CheckResult(
            name="tooling.precommit_mypy",
            category="tooling",
            passed=False,
            weight=2,
            message="No mypy hook in pre-commit",
            details=["mirrors-mypy hook should be configured"],
            fix="Add pre-commit/mirrors-mypy repo with mypy hook.",
        )
    return CheckResult(
        name="tooling.precommit_mypy",
        category="tooling",
        passed=True,
        weight=2,
        message="MyPy hook present",
        details=[],
        fix="",
    )


def check_precommit_conventional(project: Path) -> CheckResult:
    """Check 16: conventional-pre-commit hook present."""
    content = _read_precommit(project)
    if content is None or "conventional-pre-commit" not in content:
        return CheckResult(
            name="tooling.precommit_conventional",
            category="tooling",
            passed=False,
            weight=2,
            message="No conventional-commits hook in pre-commit",
            details=["conventional-pre-commit hook enforces commit message format"],
            fix="Add compilerla/conventional-pre-commit repo.",
        )
    return CheckResult(
        name="tooling.precommit_conventional",
        category="tooling",
        passed=True,
        weight=2,
        message="Conventional commits hook present",
        details=[],
        fix="",
    )


def check_precommit_basic(project: Path) -> CheckResult:
    """Check 17: basic hooks (trailing-whitespace, end-of-file-fixer, check-yaml)."""
    content = _read_precommit(project)
    required = ["trailing-whitespace", "end-of-file-fixer", "check-yaml"]
    if content is None:
        return CheckResult(
            name="tooling.precommit_basic",
            category="tooling",
            passed=False,
            weight=1,
            message="No pre-commit config",
            details=[f"Missing: {', '.join(required)}"],
            fix="Add pre-commit-hooks repo with basic hooks.",
        )
    missing = [h for h in required if h not in content]
    if missing:
        return CheckResult(
            name="tooling.precommit_basic",
            category="tooling",
            passed=False,
            weight=1,
            message=f"Missing {len(missing)} basic hook(s)",
            details=[f"Missing: {', '.join(missing)}"],
            fix=f"Add {', '.join(missing)} to pre-commit-hooks.",
        )
    return CheckResult(
        name="tooling.precommit_basic",
        category="tooling",
        passed=True,
        weight=1,
        message="Basic hooks present",
        details=[],
        fix="",
    )


def check_precommit_installed(project: Path) -> CheckResult:
    """Check 19: pre-commit hooks activated in .git/hooks/."""
    config = project / ".pre-commit-config.yaml"
    if not config.exists():
        return CheckResult(
            name="tooling.precommit_installed",
            category="tooling",
            passed=True,
            weight=2,
            message="No pre-commit config (nothing to install)",
            details=[],
            fix="",
        )
    hook = project / ".git" / "hooks" / "pre-commit"
    if hook.exists():
        return CheckResult(
            name="tooling.precommit_installed",
            category="tooling",
            passed=True,
            weight=2,
            message="Pre-commit hooks installed",
            details=[],
            fix="",
        )
    return CheckResult(
        name="tooling.precommit_installed",
        category="tooling",
        passed=False,
        weight=2,
        message="Pre-commit hooks not installed",
        details=[".pre-commit-config.yaml exists but hooks are not activated"],
        fix="Run 'pre-commit install' to activate hooks.",
    )


def check_makefile(project: Path) -> CheckResult:
    """Check 18: Makefile with standard targets."""
    path = project / "Makefile"
    if not path.exists():
        return CheckResult(
            name="tooling.makefile",
            category="tooling",
            passed=False,
            weight=4,
            message="Makefile not found",
            details=[],
            fix=(
                "Create a Makefile with install, check,"
                " lint, format, test, audit, clean,"
                " docs-serve targets."
            ),
        )
    content = path.read_text()
    required_targets = [
        "install",
        "check",
        "lint",
        "format",
        "test",
        "audit",
        "clean",
        "docs-serve",
    ]
    missing = [t for t in required_targets if f"{t}:" not in content]
    if missing:
        return CheckResult(
            name="tooling.makefile",
            category="tooling",
            passed=False,
            weight=4,
            message=f"Makefile missing {len(missing)} target(s)",
            details=[f"Missing targets: {', '.join(missing)}"],
            fix=f"Add targets to Makefile: {', '.join(missing)}.",
        )
    return CheckResult(
        name="tooling.makefile",
        category="tooling",
        passed=True,
        weight=4,
        message="Makefile complete",
        details=[],
        fix="",
    )
