"""Audit checks for dependency hygiene (2 checks, 5 pts)."""

from __future__ import annotations

from pathlib import Path

from axm_init.checks._utils import TomlTable, requires_toml, section
from axm_init.models.check import CheckResult


@requires_toml(
    check_name="deps.dev_group",
    category="deps",
    weight=3,
    fix="Create pyproject.toml with [dependency-groups] dev group.",
)
def check_dev_deps(project: Path, data: TomlTable) -> CheckResult:
    """Check 29: dev deps include pytest, ruff, mypy, and a hook runner.

    Tri-state hook-runner detection: ``prek`` passes clean, the legacy
    ``pre-commit`` passes with a soft migration warning, and neither fails.
    The warning is soft (``passed=True``) and does not dent the score.
    """
    raw_dev = section(data, "dependency-groups").get("dev", [])
    dev = raw_dev if isinstance(raw_dev, list) else []
    dev_str = " ".join(str(d) for d in dev).lower()
    base_required = ["pytest", "ruff", "mypy"]
    missing = [d for d in base_required if d not in dev_str]
    has_prek = "prek" in dev_str
    has_precommit = "pre-commit" in dev_str
    if not has_prek and not has_precommit:
        missing.append("prek")
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
    details: list[str] = []
    if not has_prek and has_precommit:
        details.append("⚠️ consider migrating to prek (uv-native, faster)")
    return CheckResult(
        name="deps.dev_group",
        category="deps",
        passed=True,
        weight=3,
        message="Dev deps complete",
        details=details,
        fix="",
    )


@requires_toml(
    check_name="deps.docs_group",
    category="deps",
    weight=2,
    fix="Create pyproject.toml with [dependency-groups] docs group.",
)
def check_docs_group(project: Path, data: TomlTable) -> CheckResult:
    """Check 30: docs deps include key packages."""
    raw_docs = section(data, "dependency-groups").get("docs", [])
    docs = raw_docs if isinstance(raw_docs, list) else []
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
