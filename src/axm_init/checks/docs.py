"""Audit checks for documentation (5 checks, 14 pts)."""

from __future__ import annotations

from pathlib import Path

from axm_init.models.check import CheckResult


def check_mkdocs_exists(project: Path) -> CheckResult:
    """Check 19: mkdocs.yml exists."""
    if not (project / "mkdocs.yml").exists():
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
    path = project / "mkdocs.yml"
    if not path.exists():
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
    """Check 21: gen-files + literate-nav + mkdocstrings."""
    path = project / "mkdocs.yml"
    if not path.exists():
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
    if not (project / "docs" / "gen_ref_pages.py").exists():
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
