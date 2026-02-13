"""Audit checks for project structure (7 checks, 17 pts)."""

from __future__ import annotations

from pathlib import Path

from axm_init.models.check import CheckResult


def check_src_layout(project: Path) -> CheckResult:
    """Check 24: src/<pkg>/ layout with __init__.py."""
    src = project / "src"
    if not src.is_dir():
        return CheckResult(
            name="structure.src_layout",
            category="structure",
            passed=False,
            weight=4,
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
            weight=4,
            message="No Python package found in src/",
            details=["src/ exists but contains no package with __init__.py"],
            fix="Create src/<package_name>/__init__.py.",
        )
    return CheckResult(
        name="structure.src_layout",
        category="structure",
        passed=True,
        weight=4,
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


def _find_uv_lock(project: Path) -> Path | None:
    """Locate uv.lock: local first, then workspace root.

    In a uv workspace (monorepo), ``uv.lock`` lives at the workspace root,
    not in each member package.  Walk up parent directories looking for a
    ``pyproject.toml`` that contains ``[tool.uv.workspace]`` and a sibling
    ``uv.lock``.
    """
    local = project / "uv.lock"
    if local.exists():
        return local
    for parent in project.resolve().parents:
        candidate = parent / "pyproject.toml"
        if candidate.exists():
            try:
                text = candidate.read_text()
                if "[tool.uv.workspace]" in text:
                    lock = parent / "uv.lock"
                    if lock.exists():
                        return lock
                    return None  # workspace root found but no lock
            except OSError:
                continue
    return None


def check_uv_lock(project: Path) -> CheckResult:
    """Check 32: uv.lock committed for reproducible builds."""
    lock = _find_uv_lock(project)
    if lock is None:
        return CheckResult(
            name="structure.uv_lock",
            category="structure",
            passed=False,
            weight=2,
            message="uv.lock not found",
            details=["Commit uv.lock for reproducible dependency resolution"],
            fix="Run `uv lock` and commit the generated uv.lock file.",
        )
    at_root = lock.parent != project.resolve()
    msg = "uv.lock found (workspace root)" if at_root else "uv.lock found"
    return CheckResult(
        name="structure.uv_lock",
        category="structure",
        passed=True,
        weight=2,
        message=msg,
        details=[],
        fix="",
    )


def check_python_version(project: Path) -> CheckResult:
    """Check 33: .python-version file exists."""
    if not (project / ".python-version").exists():
        return CheckResult(
            name="structure.python_version",
            category="structure",
            passed=False,
            weight=1,
            message=".python-version not found",
            details=["Pin Python version for consistent environments"],
            fix="Run `uv python pin 3.12` to create .python-version.",
        )
    return CheckResult(
        name="structure.python_version",
        category="structure",
        passed=True,
        weight=1,
        message=".python-version found",
        details=[],
        fix="",
    )
