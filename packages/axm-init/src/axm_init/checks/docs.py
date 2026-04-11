"""Audit checks for documentation (6 checks, 16 pts)."""

from __future__ import annotations

import logging
from pathlib import Path

from axm_init.models.check import CheckResult

logger = logging.getLogger(__name__)

__all__ = [
    "check_diataxis_nav",
    "check_docs_gen_ref_pages",
    "check_docs_plugins",
    "check_mkdocs_exists",
    "check_readme",
    "check_readme_badges",
]


def _resolve_mkdocs(project: Path) -> Path | None:
    """Resolve mkdocs.yml, falling back to workspace root for workspace members."""
    local = project / "mkdocs.yml"
    if local.exists():
        return local
    if project.parent.name == "packages":
        workspace_root = project.parent.parent
        candidate = workspace_root / "mkdocs.yml"
        if candidate.exists():
            return candidate
    return None


def check_mkdocs_exists(project: Path) -> CheckResult:
    """Check 19: mkdocs.yml exists."""
    if not _resolve_mkdocs(project):
        return CheckResult(
            name="docs.mkdocs_exists",
            category="docs",
            passed=False,
            weight=3,
            message="mkdocs.yml not found",
            details=[],
            fix="Create mkdocs.yml with Material theme and Diátaxis navigation.",
        )
    return CheckResult(
        name="docs.mkdocs_exists",
        category="docs",
        passed=True,
        weight=3,
        message="mkdocs.yml found",
        details=[],
        fix="",
    )


def check_diataxis_nav(project: Path) -> CheckResult:
    """Check 20: nav has Tutorials + How-To + Reference + Explanation."""
    path = _resolve_mkdocs(project)
    if not path:
        return CheckResult(
            name="docs.diataxis_nav",
            category="docs",
            passed=False,
            weight=3,
            message="mkdocs.yml not found",
            details=[],
            fix="Create mkdocs.yml with Diátaxis nav structure.",
        )
    content = path.read_text().lower()
    sections = {
        "Tutorials": "tutorial" in content,
        "How-To": "how-to" in content or "howto" in content,
        "Reference": "reference" in content,
        "Explanation": "explanation" in content,
    }
    missing = [s for s, present in sections.items() if not present]
    if missing:
        return CheckResult(
            name="docs.diataxis_nav",
            category="docs",
            passed=False,
            weight=3,
            message=f"Diátaxis nav incomplete — missing {len(missing)} section(s)",
            details=[
                f"Missing: {', '.join(missing)}",
                f"Present: {', '.join(s for s, p in sections.items() if p)}",
            ],
            fix=f"Add {', '.join(missing)} section(s) to mkdocs.yml nav.",
        )
    return CheckResult(
        name="docs.diataxis_nav",
        category="docs",
        passed=True,
        weight=3,
        message="Full Diátaxis nav structure",
        details=[],
        fix="",
    )


def check_docs_plugins(project: Path) -> CheckResult:
    """Check 21: gen-files + literate-nav + mkdocstrings.

    For workspace members (``project.parent.name == "packages"``), missing
    plugins are re-checked against the workspace-root ``mkdocs.yml`` so that
    nav-only local configs do not trigger false positives.
    """
    path = _resolve_mkdocs(project)
    if not path:
        return CheckResult(
            name="docs.plugins",
            category="docs",
            passed=False,
            weight=3,
            message="mkdocs.yml not found",
            details=[],
            fix="Create mkdocs.yml with gen-files, literate-nav, mkdocstrings plugins.",
        )
    content = path.read_text()
    required = {
        "gen-files": "gen-files" in content,
        "literate-nav": "literate-nav" in content,
        "mkdocstrings": "mkdocstrings" in content,
    }
    missing = [p for p, present in required.items() if not present]
    if missing and project.parent.name == "packages":
        root_mkdocs = project.parent.parent / "mkdocs.yml"
        if root_mkdocs.exists():
            root_content = root_mkdocs.read_text()
            missing = [p for p in missing if p not in root_content]
    if missing:
        return CheckResult(
            name="docs.plugins",
            category="docs",
            passed=False,
            weight=3,
            message=f"Missing {len(missing)} plugin(s)",
            details=[f"Missing: {', '.join(missing)}"],
            fix=f"Add {', '.join(missing)} to mkdocs.yml plugins.",
        )
    return CheckResult(
        name="docs.plugins",
        category="docs",
        passed=True,
        weight=3,
        message="All plugins configured",
        details=[],
        fix="",
    )


def check_docs_gen_ref_pages(project: Path) -> CheckResult:
    """Check 22: docs/gen_ref_pages.py exists."""
    found = (project / "docs" / "gen_ref_pages.py").exists()
    if not found and project.parent.name == "packages":
        workspace_root = project.parent.parent
        found = (workspace_root / "docs" / "gen_ref_pages.py").exists()
    if not found:
        return CheckResult(
            name="docs.gen_ref_pages",
            category="docs",
            passed=False,
            weight=2,
            message="docs/gen_ref_pages.py not found",
            details=["Auto-gen script needed for mkdocstrings API reference"],
            fix="Create docs/gen_ref_pages.py for automatic API reference generation.",
        )
    return CheckResult(
        name="docs.gen_ref_pages",
        category="docs",
        passed=True,
        weight=2,
        message="gen_ref_pages.py found",
        details=[],
        fix="",
    )


def check_readme(project: Path) -> CheckResult:
    """Check 23: README.md sections."""
    path = project / "README.md"
    if not path.exists():
        return CheckResult(
            name="docs.readme",
            category="docs",
            passed=False,
            weight=3,
            message="README.md not found",
            details=[],
            fix="Create README.md following axm-bib standard.",
        )
    content = path.read_text()
    required = {
        "Features": "## Features" in content or "## features" in content.lower(),
        "Installation": "## Installation" in content or "## install" in content.lower(),
        "Development": "## Development" in content or "## develop" in content.lower(),
        "License": "## License" in content or "## license" in content.lower(),
    }
    missing = [s for s, present in required.items() if not present]
    if missing:
        return CheckResult(
            name="docs.readme",
            category="docs",
            passed=False,
            weight=3,
            message=f"README missing {len(missing)} section(s)",
            details=[f"Missing: {', '.join(missing)}"],
            fix=f"Add {', '.join(missing)} section(s) to README.md.",
        )
    return CheckResult(
        name="docs.readme",
        category="docs",
        passed=True,
        weight=3,
        message="README follows standard",
        details=[],
        fix="",
    )


def check_readme_badges(project: Path) -> CheckResult:
    """Check 24: README has axm-audit + axm-init badges."""
    path = project / "README.md"
    if not path.exists():
        return CheckResult(
            name="docs.readme_badges",
            category="docs",
            passed=False,
            weight=2,
            message="README.md not found",
            details=[],
            fix="Create README.md with axm-audit and axm-init badges.",
        )
    content = path.read_text()
    required = {
        "axm-audit": "axm-audit" in content,
        "axm-init": "axm-init" in content,
    }
    missing = [b for b, present in required.items() if not present]
    if missing:
        return CheckResult(
            name="docs.readme_badges",
            category="docs",
            passed=False,
            weight=2,
            message=f"README missing {len(missing)} badge(s)",
            details=[f"Missing: {', '.join(missing)}"],
            fix=f"Add {', '.join(missing)} badge(s) to README.md.",
        )
    return CheckResult(
        name="docs.readme_badges",
        category="docs",
        passed=True,
        weight=2,
        message="README has axm-audit + axm-init badges",
        details=[],
        fix="",
    )
