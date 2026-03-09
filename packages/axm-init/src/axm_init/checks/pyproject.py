"""Audit checks for pyproject.toml (9 checks, 27 pts)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from axm_init.checks._utils import _load_toml, requires_toml
from axm_init.models.check import CheckResult

logger = logging.getLogger(__name__)


def check_pyproject_exists(project: Path) -> CheckResult:
    """Check 1: pyproject.toml exists and is parsable."""
    path = project / "pyproject.toml"
    if not path.exists():
        return CheckResult(
            name="pyproject.exists",
            category="pyproject",
            passed=False,
            weight=4,
            message="pyproject.toml not found",
            details=[],
            fix="Create a pyproject.toml at the project root.",
        )
    data = _load_toml(project)
    if data is None:
        return CheckResult(
            name="pyproject.exists",
            category="pyproject",
            passed=False,
            weight=4,
            message="pyproject.toml is unparsable",
            details=["File exists but contains invalid TOML"],
            fix="Fix TOML syntax errors in pyproject.toml.",
        )
    return CheckResult(
        name="pyproject.exists",
        category="pyproject",
        passed=True,
        weight=4,
        message="pyproject.toml found",
        details=[],
        fix="",
    )


@requires_toml(
    check_name="pyproject.urls",
    category="pyproject",
    weight=3,
    fix="Create pyproject.toml with [project.urls] section.",
)
def check_pyproject_urls(project: Path, data: dict[str, Any]) -> CheckResult:
    """Check 2: [project.urls] with 4 keys."""
    required = {"Homepage", "Documentation", "Repository", "Issues"}
    urls = data.get("project", {}).get("urls", {})
    present = set(urls.keys()) & required
    missing = required - present
    if missing:
        return CheckResult(
            name="pyproject.urls",
            category="pyproject",
            passed=False,
            weight=3,
            message=f"Missing {len(missing)} URL(s) in [project.urls]",
            details=[
                f"Missing: {', '.join(sorted(missing))}",
                f"Present: {', '.join(sorted(present))}",
            ],
            fix=(
                f"Add {', '.join(sorted(missing))} to [project.urls] in pyproject.toml."
            ),
        )
    return CheckResult(
        name="pyproject.urls",
        category="pyproject",
        passed=True,
        weight=3,
        message="All 4 URLs present",
        details=[],
        fix="",
    )


@requires_toml(
    check_name="pyproject.dynamic_version",
    category="pyproject",
    weight=3,
    fix="Create pyproject.toml with dynamic version using hatch-vcs.",
)
def check_pyproject_dynamic_version(project: Path, data: dict[str, Any]) -> CheckResult:
    """Check 3: dynamic = ['version'] + hatch-vcs."""
    dynamic = data.get("project", {}).get("dynamic", [])
    requires = data.get("build-system", {}).get("requires", [])
    has_dynamic = "version" in dynamic
    has_hatch_vcs = any("hatch-vcs" in r for r in requires)
    problems = []
    if not has_dynamic:
        problems.append('Missing: dynamic = ["version"]')
    if not has_hatch_vcs:
        problems.append("Missing: hatch-vcs in build-system.requires")
    if problems:
        return CheckResult(
            name="pyproject.dynamic_version",
            category="pyproject",
            passed=False,
            weight=3,
            message="Version is not dynamically managed",
            details=problems,
            fix='Add hatch-vcs to build-system.requires and set dynamic = ["version"].',
        )
    return CheckResult(
        name="pyproject.dynamic_version",
        category="pyproject",
        passed=True,
        weight=3,
        message="Dynamic version with hatch-vcs",
        details=[],
        fix="",
    )


@requires_toml(
    check_name="pyproject.mypy",
    category="pyproject",
    weight=3,
    fix="Create pyproject.toml with [tool.mypy] section.",
)
def check_pyproject_mypy(project: Path, data: dict[str, Any]) -> CheckResult:
    """Check 4: strict + pretty + disallow_incomplete_defs + check_untyped_defs."""
    mypy = data.get("tool", {}).get("mypy", {})
    required = {
        "strict": True,
        "pretty": True,
        "disallow_incomplete_defs": True,
        "check_untyped_defs": True,
    }
    missing = [k for k, v in required.items() if mypy.get(k) != v]
    present = [k for k in required if k not in missing]
    if missing:
        return CheckResult(
            name="pyproject.mypy",
            category="pyproject",
            passed=False,
            weight=3,
            message=f"MyPy config incomplete — missing {len(missing)} setting(s)",
            details=[
                f"Missing: {', '.join(missing)}",
                f"Present: {', '.join(present)}",
            ],
            fix=f"Add {', '.join(f'{k} = true' for k in missing)} to [tool.mypy].",
        )
    return CheckResult(
        name="pyproject.mypy",
        category="pyproject",
        passed=True,
        weight=3,
        message="MyPy fully configured",
        details=[],
        fix="",
    )


@requires_toml(
    check_name="pyproject.ruff",
    category="pyproject",
    weight=3,
    fix="Create pyproject.toml with [tool.ruff.lint] section.",
)
def check_pyproject_ruff(project: Path, data: dict[str, Any]) -> CheckResult:
    """Check 5: per-file-ignores + known-first-party."""
    ruff_lint = data.get("tool", {}).get("ruff", {}).get("lint", {})
    problems = []
    if "per-file-ignores" not in ruff_lint:
        problems.append("Missing: [tool.ruff.lint.per-file-ignores]")
    isort = ruff_lint.get("isort", {})
    if "known-first-party" not in isort:
        problems.append("Missing: known-first-party in [tool.ruff.lint.isort]")
    if problems:
        return CheckResult(
            name="pyproject.ruff",
            category="pyproject",
            passed=False,
            weight=3,
            message="Ruff config incomplete",
            details=problems,
            fix="Add per-file-ignores for tests and known-first-party to ruff config.",
        )
    return CheckResult(
        name="pyproject.ruff",
        category="pyproject",
        passed=True,
        weight=3,
        message="Ruff fully configured",
        details=[],
        fix="",
    )


@requires_toml(
    check_name="pyproject.pytest",
    category="pyproject",
    weight=4,
    fix="Create pyproject.toml with [tool.pytest.ini_options].",
)
def check_pyproject_pytest(project: Path, data: dict[str, Any]) -> CheckResult:
    """Check 6: pytest config completeness."""
    pytest_cfg = data.get("tool", {}).get("pytest", {}).get("ini_options", {})
    addopts = " ".join(pytest_cfg.get("addopts", []))
    problems = []
    if "--strict-markers" not in addopts:
        problems.append("Missing: --strict-markers in addopts")
    if "--strict-config" not in addopts:
        problems.append("Missing: --strict-config in addopts")
    if "--import-mode=importlib" not in addopts:
        problems.append("Missing: --import-mode=importlib in addopts")
    if "pythonpath" not in pytest_cfg:
        problems.append('Missing: pythonpath = ["src"]')
    if "filterwarnings" not in pytest_cfg:
        problems.append("Missing: filterwarnings")
    if problems:
        return CheckResult(
            name="pyproject.pytest",
            category="pyproject",
            passed=False,
            weight=4,
            message=f"Pytest config incomplete — missing {len(problems)} setting(s)",
            details=problems,
            fix="Add missing settings to [tool.pytest.ini_options].",
        )
    return CheckResult(
        name="pyproject.pytest",
        category="pyproject",
        passed=True,
        weight=4,
        message="Pytest fully configured",
        details=[],
        fix="",
    )


@requires_toml(
    check_name="pyproject.coverage",
    category="pyproject",
    weight=4,
    fix="Create pyproject.toml with [tool.coverage] sections.",
)
def check_pyproject_coverage(project: Path, data: dict[str, Any]) -> CheckResult:
    """Check 7: branch, relative_files, xml output, exclude_lines."""
    cov = data.get("tool", {}).get("coverage", {})
    run_cfg = cov.get("run", {})
    problems = []
    if not run_cfg.get("branch"):
        problems.append("Missing: branch = true in [tool.coverage.run]")
    if not run_cfg.get("relative_files"):
        problems.append("Missing: relative_files = true in [tool.coverage.run]")
    if "xml" not in cov:
        problems.append("Missing: [tool.coverage.xml] section")
    if "exclude_lines" not in cov.get("report", {}):
        problems.append("Missing: exclude_lines in [tool.coverage.report]")
    if problems:
        return CheckResult(
            name="pyproject.coverage",
            category="pyproject",
            passed=False,
            weight=4,
            message=f"Coverage config incomplete — missing {len(problems)} setting(s)",
            details=problems,
            fix="Add missing settings to [tool.coverage] sections.",
        )
    return CheckResult(
        name="pyproject.coverage",
        category="pyproject",
        passed=True,
        weight=4,
        message="Coverage fully configured",
        details=[],
        fix="",
    )


@requires_toml(
    check_name="pyproject.classifiers",
    category="pyproject",
    weight=1,
    fix="Add classifiers to [project] in pyproject.toml.",
)
def check_pyproject_classifiers(project: Path, data: dict[str, Any]) -> CheckResult:
    """Check 36: required classifiers (Dev Status, Python, Typed)."""
    classifiers = data.get("project", {}).get("classifiers", [])
    required_prefixes = {
        "Development Status": "Development Status ::",
        "Python version": "Programming Language :: Python :: 3",
        "Typed": "Typing :: Typed",
    }
    missing = [
        label
        for label, prefix in required_prefixes.items()
        if not any(c.startswith(prefix) for c in classifiers)
    ]
    if missing:
        return CheckResult(
            name="pyproject.classifiers",
            category="pyproject",
            passed=False,
            weight=1,
            message=f"Missing {len(missing)} required classifier(s)",
            details=[f"Missing: {', '.join(missing)}"],
            fix=(
                "Add Development Status, Python version,"
                " and Typing :: Typed classifiers."
            ),
        )
    return CheckResult(
        name="pyproject.classifiers",
        category="pyproject",
        passed=True,
        weight=1,
        message="Required classifiers present",
        details=[],
        fix="",
    )


@requires_toml(
    check_name="pyproject.ruff_rules",
    category="pyproject",
    weight=2,
    fix="Add [tool.ruff.lint] select with E, F, I, UP, B, S, BLE, PLR, N.",
)
def check_pyproject_ruff_rules(project: Path, data: dict[str, Any]) -> CheckResult:
    """Check 37: essential ruff rule codes activated."""
    ruff_lint = data.get("tool", {}).get("ruff", {}).get("lint", {})
    select = set(ruff_lint.get("select", []))
    extend = set(ruff_lint.get("extend-select", []))
    all_rules = select | extend
    required = {"E", "F", "I", "UP", "B", "S", "BLE", "PLR", "N"}
    # "ALL" includes everything
    if "ALL" in all_rules:
        missing: set[str] = set()
    else:
        missing = required - all_rules
    if missing:
        return CheckResult(
            name="pyproject.ruff_rules",
            category="pyproject",
            passed=False,
            weight=2,
            message=f"Missing {len(missing)} essential ruff rule(s)",
            details=[f"Missing: {', '.join(sorted(missing))}"],
            fix=f"Add {', '.join(sorted(missing))} to [tool.ruff.lint] select.",
        )
    return CheckResult(
        name="pyproject.ruff_rules",
        category="pyproject",
        passed=True,
        weight=2,
        message="Essential ruff rules activated",
        details=[],
        fix="",
    )
