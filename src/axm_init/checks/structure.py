"""Audit checks for project structure (5 checks, 15 pts)."""

from __future__ import annotations

from pathlib import Path

from axm_init.models.audit import CheckResult


def check_src_layout(project: Path) -> CheckResult:
    """Check 24: src/<pkg>/ layout with __init__.py."""
    src = project / "src"
    if not src.is_dir():
        return CheckResult(
            name="structure.src_layout",
            category="structure",
            passed=False,
            weight=5,
            message="src/ directory not found",
            details=["Expected: src/<package_name>/__init__.py"],
            fix="Migrate to src/ layout: move package into src/<package_name>/.",
        )
    # Find at least one package (dir with __init__.py) under src/
    packages = [d for d in src.iterdir() if d.is_dir() and (d / "__init__.py").exists()]
    if not packages:
        return CheckResult(
            name="structure.src_layout",
            category="structure",
            passed=False,
            weight=5,
            message="No Python package found in src/",
            details=["src/ exists but contains no package with __init__.py"],
            fix="Create src/<package_name>/__init__.py.",
        )
    return CheckResult(
        name="structure.src_layout",
        category="structure",
        passed=True,
        weight=5,
        message=f"src/ layout with {len(packages)} package(s)",
        details=[],
        fix="",
    )


def check_py_typed(project: Path) -> CheckResult:
    """Check 25: py.typed marker in package."""
    src = project / "src"
    if not src.is_dir():
        return CheckResult(
            name="structure.py_typed",
            category="structure",
            passed=False,
            weight=2,
            message="src/ directory not found",
            details=[],
            fix="Create src/<package_name>/py.typed marker file.",
        )
    packages = [d for d in src.iterdir() if d.is_dir() and (d / "__init__.py").exists()]
    for pkg in packages:
        if (pkg / "py.typed").exists():
            return CheckResult(
                name="structure.py_typed",
                category="structure",
                passed=True,
                weight=2,
                message="py.typed marker found",
                details=[],
                fix="",
            )
    return CheckResult(
        name="structure.py_typed",
        category="structure",
        passed=False,
        weight=2,
        message="py.typed marker not found",
        details=["PEP 561: py.typed marks package as providing type information"],
        fix="Create an empty src/<package_name>/py.typed file.",
    )


def check_tests_dir(project: Path) -> CheckResult:
    """Check 26: tests/ directory with at least one test file."""
    tests = project / "tests"
    if not tests.is_dir():
        return CheckResult(
            name="structure.tests_dir",
            category="structure",
            passed=False,
            weight=3,
            message="tests/ directory not found",
            details=[],
            fix="Create tests/ directory with test files.",
        )
    test_files = list(tests.rglob("test_*.py"))
    if not test_files:
        return CheckResult(
            name="structure.tests_dir",
            category="structure",
            passed=False,
            weight=3,
            message="No test files found in tests/",
            details=["Expected: tests/test_*.py files"],
            fix="Add test files matching test_*.py pattern.",
        )
    return CheckResult(
        name="structure.tests_dir",
        category="structure",
        passed=True,
        weight=3,
        message=f"{len(test_files)} test file(s) found",
        details=[],
        fix="",
    )


def check_contributing(project: Path) -> CheckResult:
    """Check 27: CONTRIBUTING.md exists."""
    if not (project / "CONTRIBUTING.md").exists():
        return CheckResult(
            name="structure.contributing",
            category="structure",
            passed=False,
            weight=2,
            message="CONTRIBUTING.md not found",
            details=[],
            fix="Create CONTRIBUTING.md with dev setup and commit conventions.",
        )
    return CheckResult(
        name="structure.contributing",
        category="structure",
        passed=True,
        weight=2,
        message="CONTRIBUTING.md found",
        details=[],
        fix="",
    )


def check_license_file(project: Path) -> CheckResult:
    """Check 28: LICENSE file exists."""
    if not (project / "LICENSE").exists():
        return CheckResult(
            name="structure.license",
            category="structure",
            passed=False,
            weight=3,
            message="LICENSE file not found",
            details=[],
            fix="Create a LICENSE file (MIT, Apache-2.0, or EUPL-1.2).",
        )
    return CheckResult(
        name="structure.license",
        category="structure",
        passed=True,
        weight=3,
        message="LICENSE file found",
        details=[],
        fix="",
    )
