"""Check engine — orchestrates all checks and produces ProjectResult."""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import axm_init.checks as _checks_pkg
from axm_init.checks._utils import load_exclusions
from axm_init.checks._workspace import (
    ProjectContext,
    detect_context,
    find_workspace_root,
)
from axm_init.models.check import CheckResult, ProjectResult

logger = logging.getLogger(__name__)

# Checks to skip for workspace roots (they are package-level concerns).
SKIP_FOR_WORKSPACE: frozenset[str] = frozenset(
    {
        "structure.src_layout",
        "structure.py_typed",
        "structure.tests_dir",
        "pyproject.pyproject_urls",
        "pyproject.pyproject_dynamic_version",
        "pyproject.pyproject_classifiers",
        "pyproject.pyproject_mypy",
        "pyproject.pyproject_ruff",
        "pyproject.pyproject_ruff_rules",
        "changelog.gitcliff_config",
        "deps.dev_deps",
        "deps.docs_deps",
        "pyproject.pyproject_pytest",
        "pyproject.pyproject_coverage",
        "docs.diataxis_nav",
    }
)

# CI/tooling checks that should be redirected to workspace root for members.
REDIRECT_FOR_MEMBER: frozenset[str] = frozenset(
    {
        "ci.ci_workflow_exists",
        "ci.trusted_publishing",
        "ci.dependabot",
        "ci.ci_lint_job",
        "ci.ci_security_job",
        "ci.ci_coverage_upload",
        "ci.ci_test_job",
        "tooling.precommit_exists",
        "tooling.precommit_ruff",
        "tooling.precommit_mypy",
        "tooling.precommit_conventional",
        "tooling.precommit_basic",
        "tooling.makefile",
        "tooling.precommit_installed",
        "structure.license_file",
        "structure.python_version",
        "structure.contributing",
    }
)


def _discover_checks() -> dict[str, list[Callable[[Path], CheckResult]]]:
    """Auto-discover ``check_*`` functions from all modules in ``axm_init.checks``.

    Scans every public module in the ``checks`` package (skipping private
    ``_``-prefixed modules) and collects all public ``check_*`` functions.
    The module name becomes the category key.
    """
    registry: dict[str, list[Callable[[Path], CheckResult]]] = {}
    for info in pkgutil.iter_modules(_checks_pkg.__path__):
        if info.name.startswith("_"):
            continue  # Skip private modules like _utils
        module_path = f"axm_init.checks.{info.name}"
        mod = importlib.import_module(module_path)
        fns: list[Callable[[Path], CheckResult]] = [
            obj
            for name, obj in inspect.getmembers(mod, inspect.isfunction)
            if name.startswith("check_") and not name.startswith("_")
        ]
        if fns:
            registry[info.name] = fns
    return registry


def _get_check_name(fn: Callable[[Path], CheckResult]) -> str | None:
    """Infer check name by calling the function on a dummy path.

    We use the function's module and name to build the check name
    following the convention: ``category.function_name_without_check_``.
    """
    module = getattr(fn, "__module__", "")
    category = module.rsplit(".", 1)[-1] if module else ""
    fn_name = getattr(fn, "__name__", "")
    if fn_name.startswith("check_"):
        return f"{category}.{fn_name[6:]}"
    return None


def _make_excluded_result(check_name: str, category: str) -> CheckResult:
    """Create an auto-pass result for an excluded check."""
    return CheckResult(
        name=check_name,
        category=category,
        passed=True,
        weight=0,
        message="Excluded by config",
        details=[],
        fix="",
    )


def _redirect_to_root(
    fn: Callable[[Path], CheckResult],
    workspace_root: Path,
) -> Callable[[Path], CheckResult]:
    """Wrap a check function to run against the workspace root."""

    def wrapper(_project: Path) -> CheckResult:
        """Delegate check to workspace root."""
        return fn(workspace_root)

    # Preserve function metadata for check name inference
    wrapper.__name__ = fn.__name__
    wrapper.__module__ = fn.__module__
    return wrapper


# Registry: category -> list of check functions
ALL_CHECKS: dict[str, list[Callable[[Path], CheckResult]]] = _discover_checks()

VALID_CATEGORIES = set(ALL_CHECKS.keys())


class CheckEngine:
    """Orchestrates project checks and produces results."""

    def __init__(self, project_path: Path, *, category: str | None = None) -> None:
        self.project_path = project_path.resolve()
        self.category = category
        self.context = detect_context(self.project_path)
        self.workspace_root = find_workspace_root(self.project_path)

    def _is_excluded(self, check_name: str, exclusions: set[str]) -> bool:
        """Check if a check name matches any exclusion prefix."""
        return any(check_name.startswith(prefix) for prefix in exclusions)

    def _should_skip(self, check_name: str | None, category: str) -> bool:
        """Return True if the check should be skipped for context reasons."""
        if category == "workspace" and self.context != ProjectContext.WORKSPACE:
            return True
        return (
            self.context == ProjectContext.WORKSPACE
            and check_name in SKIP_FOR_WORKSPACE
        )

    def _should_redirect(self, check_name: str | None) -> bool:
        """Return True if the check should be redirected to workspace root."""
        return (
            self.context == ProjectContext.MEMBER
            and check_name in REDIRECT_FOR_MEMBER
            and self.workspace_root is not None
        )

    def _filter_checks(
        self,
        checks_to_run: dict[str, list[Callable[[Path], CheckResult]]],
        exclusions: set[str],
    ) -> tuple[list[Callable[[Path], CheckResult]], list[CheckResult], list[str]]:
        """Apply context-aware filtering, exclusions, and redirects."""
        all_fns: list[Callable[[Path], CheckResult]] = []
        excluded_results: list[CheckResult] = []
        excluded_names: list[str] = []

        for category, fns in checks_to_run.items():
            for fn in fns:
                check_name = _get_check_name(fn)

                if check_name and self._is_excluded(check_name, exclusions):
                    excluded_results.append(_make_excluded_result(check_name, category))
                    excluded_names.append(check_name)
                elif self._should_skip(check_name, category):
                    pass
                elif self._should_redirect(check_name):
                    all_fns.append(_redirect_to_root(fn, self.workspace_root))  # type: ignore[arg-type]
                else:
                    all_fns.append(fn)

        return all_fns, excluded_results, excluded_names

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

        exclusions = load_exclusions(self.project_path)
        all_fns, excluded_results, excluded_names = self._filter_checks(
            checks_to_run, exclusions
        )

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda fn: fn(self.project_path), all_fns))

        results.extend(excluded_results)

        return ProjectResult.from_checks(
            self.project_path,
            results,
            context=self.context.value,
            workspace_root=self.workspace_root,
            excluded_checks=excluded_names,
        )


def _format_category_checks(
    checks: list[CheckResult],
    *,
    verbose: bool,
) -> list[str]:
    """Format check lines for a single category."""
    lines: list[str] = []
    if verbose:
        for check in checks:
            status = "✅" if check.passed else "❌"
            earned = f"{check.earned}/{check.weight}"
            lines.append(
                f"    {status} {check.name:<30s} {earned:>5s}  {check.message}"
            )
    else:
        passed_count = sum(1 for c in checks if c.passed)
        if passed_count:
            lines.append(f"    ✅ {passed_count} checks passed")
        for check in checks:
            if not check.passed:
                earned = f"{check.earned}/{check.weight}"
                lines.append(f"    ❌ {check.name:<30s} {earned:>5s}  {check.message}")
    return lines


def _format_failures(failures: list[CheckResult]) -> list[str]:
    """Format the failure detail block."""
    lines: list[str] = [f"  📝 Failures ({len(failures)}):", ""]
    for f in failures:
        lines.append(f"  ❌ {f.name} ({f.weight} pts)")
        lines.append(f"     Problem: {f.message}")
        for detail in f.details:
            lines.append(f"     {detail}")
        lines.append(f"     Fix:     {f.fix}")
        lines.append("")
    return lines


def format_report(result: ProjectResult, *, verbose: bool = False) -> str:
    """Format check result as human-readable report.

    Args:
        result: Project check result.
        verbose: If True, list every individual check.
            If False (default), only show summary for passing categories
            and detail for failures.
    """
    lines: list[str] = [
        f"📋 AXM Check — {result.project_path.name}",
        f"   Path: {result.project_path}",
    ]

    if result.context:
        ctx_line = f"   Context: {result.context.upper()}"
        if result.workspace_root:
            ctx_line += f" (root: {result.workspace_root})"
        lines.append(ctx_line)

    lines.append("")

    # Category breakdown
    for cat_name, cat_score in result.categories.items():
        cat_checks = [c for c in result.checks if c.category == cat_name]
        lines.append(f"  {cat_name} ({cat_score.earned}/{cat_score.total})")
        lines.extend(_format_category_checks(cat_checks, verbose=verbose))
        lines.append("")

    # Score
    grade_emoji = {"A": "🏆", "B": "✅", "C": "⚠️", "D": "🔧", "F": "❌"}
    emoji = grade_emoji.get(result.grade.value, "")
    lines.append(f"  Score: {result.score}/100 — Grade {result.grade.value} {emoji}")
    lines.append("")

    # Failures
    if result.failures:
        lines.extend(_format_failures(result.failures))

    return "\n".join(lines)


def format_json(result: ProjectResult) -> dict[str, Any]:
    """Format check result as JSON-serializable dict."""
    return {
        "project": str(result.project_path),
        "score": result.score,
        "grade": result.grade.value,
        "context": result.context,
        "workspace_root": str(result.workspace_root) if result.workspace_root else None,
        "excluded_checks": result.excluded_checks,
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
        "context": result.context,
        "workspace_root": str(result.workspace_root) if result.workspace_root else None,
        "excluded_checks": result.excluded_checks,
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
