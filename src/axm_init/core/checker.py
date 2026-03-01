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
from axm_init.models.check import CheckResult, ProjectResult

logger = logging.getLogger(__name__)


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


# Registry: category -> list of check functions
ALL_CHECKS: dict[str, list[Callable[[Path], CheckResult]]] = _discover_checks()

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
        all_fns = [fn for check_fns in checks_to_run.values() for fn in check_fns]

        with ThreadPoolExecutor() as pool:
            results = list(pool.map(lambda fn: fn(self.project_path), all_fns))

        return ProjectResult.from_checks(self.project_path, results)


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
        "",
    ]

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
