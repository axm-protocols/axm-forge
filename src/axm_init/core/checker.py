"""Check engine — orchestrates all checks and produces ProjectResult."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from axm_init.checks.changelog import check_gitcliff_config, check_no_manual_changelog
from axm_init.checks.ci import (
    check_ci_coverage_upload,
    check_ci_lint_job,
    check_ci_security_job,
    check_ci_test_job,
    check_ci_workflow_exists,
    check_dependabot,
    check_trusted_publishing,
)
from axm_init.checks.deps import check_dev_deps, check_docs_deps
from axm_init.checks.docs import (
    check_diataxis_nav,
    check_docs_gen_ref_pages,
    check_docs_plugins,
    check_mkdocs_exists,
    check_readme,
)
from axm_init.checks.pyproject import (
    check_pyproject_classifiers,
    check_pyproject_coverage,
    check_pyproject_dynamic_version,
    check_pyproject_exists,
    check_pyproject_mypy,
    check_pyproject_pytest,
    check_pyproject_ruff,
    check_pyproject_ruff_rules,
    check_pyproject_urls,
)
from axm_init.checks.structure import (
    check_contributing,
    check_license_file,
    check_py_typed,
    check_python_version,
    check_src_layout,
    check_tests_dir,
    check_uv_lock,
)
from axm_init.checks.tooling import (
    check_makefile,
    check_precommit_basic,
    check_precommit_conventional,
    check_precommit_exists,
    check_precommit_installed,
    check_precommit_mypy,
    check_precommit_ruff,
)
from axm_init.models.check import CheckResult, ProjectResult

# Registry: category -> list of check functions
ALL_CHECKS: dict[str, list[Callable[[Path], CheckResult]]] = {
    "pyproject": [
        check_pyproject_exists,
        check_pyproject_urls,
        check_pyproject_dynamic_version,
        check_pyproject_mypy,
        check_pyproject_ruff,
        check_pyproject_pytest,
        check_pyproject_coverage,
        check_pyproject_classifiers,
        check_pyproject_ruff_rules,
    ],
    "ci": [
        check_ci_workflow_exists,
        check_ci_lint_job,
        check_ci_test_job,
        check_ci_security_job,
        check_ci_coverage_upload,
        check_trusted_publishing,
        check_dependabot,
    ],
    "tooling": [
        check_precommit_exists,
        check_precommit_ruff,
        check_precommit_mypy,
        check_precommit_conventional,
        check_precommit_basic,
        check_precommit_installed,
        check_makefile,
    ],
    "docs": [
        check_mkdocs_exists,
        check_diataxis_nav,
        check_docs_plugins,
        check_docs_gen_ref_pages,
        check_readme,
    ],
    "structure": [
        check_src_layout,
        check_py_typed,
        check_tests_dir,
        check_contributing,
        check_license_file,
        check_uv_lock,
        check_python_version,
    ],
    "deps": [
        check_dev_deps,
        check_docs_deps,
    ],
    "changelog": [
        check_gitcliff_config,
        check_no_manual_changelog,
    ],
}

VALID_CATEGORIES = set(ALL_CHECKS.keys())


class CheckEngine:
    """Orchestrates project checks and produces results."""

    def __init__(self, project_path: Path, *, category: str | None = None) -> None:
        self.project_path = project_path.resolve()
        self.category = category

    def run(self) -> ProjectResult:
        """Run all checks (or filtered by category) and return result."""
        if self.category:
            if self.category not in VALID_CATEGORIES:
                valid = ", ".join(sorted(VALID_CATEGORIES))
                msg = f"Unknown category '{self.category}'. Valid: {valid}"
                raise ValueError(msg)
            checks_to_run = {self.category: ALL_CHECKS[self.category]}
        else:
            checks_to_run = ALL_CHECKS

        results: list[CheckResult] = []
        for check_fns in checks_to_run.values():
            for fn in check_fns:
                results.append(fn(self.project_path))

        return ProjectResult.from_checks(self.project_path, results)


def format_report(result: ProjectResult, *, verbose: bool = False) -> str:
    """Format check result as human-readable report.

    Args:
        result: Project check result.
        verbose: If True, list every individual check.
            If False (default), only show summary for passing categories
            and detail for failures.
    """
    lines: list[str] = []
    lines.append(f"📋 AXM Check — {result.project_path.name}")
    lines.append(f"   Path: {result.project_path}")
    lines.append("")

    # Category breakdown
    for cat_name, cat_score in result.categories.items():
        cat_checks = [c for c in result.checks if c.category == cat_name]
        passed_count = sum(1 for c in cat_checks if c.passed)
        failed_checks = [c for c in cat_checks if not c.passed]

        lines.append(f"  {cat_name} ({cat_score.earned}/{cat_score.total})")

        if verbose:
            # Show every check (original behaviour)
            for check in cat_checks:
                status = "✅" if check.passed else "❌"
                earned = f"{check.earned}/{check.weight}"
                msg = check.message
                lines.append(f"    {status} {check.name:<30s} {earned:>5s}  {msg}")
        else:
            # Compact: summarise passed, detail only failures
            if passed_count:
                lines.append(f"    ✅ {passed_count} checks passed")
            for check in failed_checks:
                earned = f"{check.earned}/{check.weight}"
                lines.append(f"    ❌ {check.name:<30s} {earned:>5s}  {check.message}")
        lines.append("")

    # Score
    grade_emoji = {"A": "🏆", "B": "✅", "C": "⚠️", "D": "🔧", "F": "❌"}
    emoji = grade_emoji.get(result.grade.value, "")
    lines.append(f"  Score: {result.score}/100 — Grade {result.grade.value} {emoji}")
    lines.append("")

    # Failures
    if result.failures:
        lines.append(f"  📝 Failures ({len(result.failures)}):")
        lines.append("")
        for f in result.failures:
            lines.append(f"  ❌ {f.name} ({f.weight} pts)")
            lines.append(f"     Problem: {f.message}")
            for detail in f.details:
                lines.append(f"     {detail}")
            lines.append(f"     Fix:     {f.fix}")
            lines.append("")

    return "\n".join(lines)


def format_json(result: ProjectResult) -> dict[str, Any]:
    """Format check result as JSON-serializable dict."""
    return {
        "project": str(result.project_path),
        "score": result.score,
        "grade": result.grade.value,
        "categories": {
            cat: {"earned": cs.earned, "total": cs.total}
            for cat, cs in result.categories.items()
        },
        "checks": [
            {
                "name": c.name,
                "category": c.category,
                "passed": c.passed,
                "earned": c.earned,
                "weight": c.weight,
                "message": c.message,
            }
            for c in result.checks
        ],
        "failures": [
            {
                "name": f.name,
                "weight": f.weight,
                "message": f.message,
                "details": f.details,
                "fix": f.fix,
            }
            for f in result.failures
        ],
    }


def format_agent(result: ProjectResult) -> dict[str, Any]:
    """Agent-optimized output: passed_count=N, failed=full detail.

    Minimizes tokens by replacing the full passed-check list with a count.
    Only failures carry actionable detail.
    """
    return {
        "score": result.score,
        "grade": result.grade.value,
        "passed_count": sum(1 for c in result.checks if c.passed),
        "failed": [
            {
                "name": f.name,
                "message": f.message,
                "details": f.details,
                "fix": f.fix,
            }
            for f in result.failures
        ],
    }
