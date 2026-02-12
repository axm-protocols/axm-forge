"""Audit checks for dependency hygiene (2 checks, 5 pts)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm_init.models.check import CheckResult

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


def _load_toml(project: Path) -> dict[str, Any] | None:
    path = project / "pyproject.toml"
    if not path.exists():
        return None
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except Exception:
        return None


def check_dev_deps(project: Path) -> CheckResult:
    """Check 29: dev deps include pytest, ruff, mypy, pre-commit."""
    data = _load_toml(project)
    if data is None:
        return CheckResult(
            name="deps.dev_group",
            category="deps",
            passed=False,
            weight=3,
            message="pyproject.toml not found or unparsable",
            details=[],
            fix="Create pyproject.toml with [dependency-groups] dev group.",
        )
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


def check_docs_deps(project: Path) -> CheckResult:
    """Check 30: docs deps include key packages."""
    data = _load_toml(project)
    if data is None:
        return CheckResult(
            name="deps.docs_group",
            category="deps",
            passed=False,
            weight=2,
            message="pyproject.toml not found or unparsable",
            details=[],
            fix="Create pyproject.toml with [dependency-groups] docs group.",
        )
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
