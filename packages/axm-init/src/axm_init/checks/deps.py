"""Audit checks for dependency hygiene (2 checks, 5 pts)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm_init.checks._utils import requires_toml
from axm_init.models.check import CheckResult


@requires_toml(
    check_name="deps.dev_group",
    category="deps",
    weight=3,
    fix="Create pyproject.toml with [dependency-groups] dev group.",
)
def check_dev_deps(project: Path, data: dict[str, Any]) -> CheckResult:
    """Check 29: dev deps include pytest, ruff, mypy, pre-commit."""
    dev = data.get("dependency-groups", {}).get("dev", [])
    dev_str = " ".join(str(d) for d in dev).lower()
    required = ["pytest", "ruff", "mypy", "pre-commit"]
    missing = [d for d in required if d not in dev_str]
    if missing:
        return CheckResult(
            name="deps.dev_group",
            category="deps",
            passed=False,
            weight=3,
            message=f"Dev group missing {len(missing)} dep(s)",
            details=[f"Missing: {', '.join(missing)}"],
            fix=f"Add {', '.join(missing)} to [dependency-groups] dev.",
        )
    return CheckResult(
        name="deps.dev_group",
        category="deps",
        passed=True,
        weight=3,
        message="Dev deps complete",
        details=[],
        fix="",
    )


@requires_toml(
    check_name="deps.docs_group",
    category="deps",
    weight=2,
    fix="Create pyproject.toml with [dependency-groups] docs group.",
)
def check_docs_deps(project: Path, data: dict[str, Any]) -> CheckResult:
    """Check 30: docs deps include key packages."""
    docs = data.get("dependency-groups", {}).get("docs", [])
    docs_str = " ".join(str(d) for d in docs).lower()
    required = [
        "mkdocs-material",
        "mkdocstrings",
        "mkdocs-gen-files",
        "mkdocs-literate-nav",
    ]
    missing = [d for d in required if d not in docs_str]
    if missing:
        return CheckResult(
            name="deps.docs_group",
            category="deps",
            passed=False,
            weight=2,
            message=f"Docs group missing {len(missing)} dep(s)",
            details=[f"Missing: {', '.join(missing)}"],
            fix=f"Add {', '.join(missing)} to [dependency-groups] docs.",
        )
    return CheckResult(
        name="deps.docs_group",
        category="deps",
        passed=True,
        weight=2,
        message="Docs deps complete",
        details=[],
        fix="",
    )
