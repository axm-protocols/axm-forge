"""Check engine — orchestrates all checks and produces ProjectResult."""

from __future__ import annotations

import importlib
import logging
import pkgutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

import axm_init.checks as _checks_pkg
from axm_init.checks._utils import load_exclusions
from axm_init.checks._workspace import (
    ProjectContext,
    detect_context,
    find_workspace_root,
)
from axm_init.models.check import CheckResult, ProjectResult

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

# Checks to skip for workspace roots (they are package-level concerns).
SKIP_FOR_WORKSPACE: frozenset[str] = frozenset(
    {
        "structure.src_layout",
        "structure.py_typed",
        "structure.tests_dir",
        "pyproject.pyproject_urls",
        "pyproject.pyproject_classifiers",
        "pyproject.pyproject_mypy",
        "pyproject.pyproject_ruff",
        "deps.dev_deps",
        "deps.docs_group",
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
    import inspect

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
    """Derive the canonical check name from the function's module + name.

    This is THE single source of truth for check naming. The convention is
    ``category.function_name_without_check_`` (the module name is the
    category). The same string is used by ``SKIP_FOR_*`` / ``REDIRECT_FOR_*``
    (pre-run, on the function), by ``[tool.axm-init].exclude`` matching
    (post-run, on the result), and as the displayed ``CheckResult.name`` —
    so a name shown in the report can always be excluded by config.
    """
    module = getattr(fn, "__module__", "")
    category = module.rsplit(".", 1)[-1] if module else ""
    fn_name = getattr(fn, "__name__", "")
    if fn_name.startswith("check_"):
        return f"{category}.{fn_name[6:]}"
    return None


def _stamp_canonical_name(
    fn: Callable[[Path], CheckResult],
    result: CheckResult,
) -> CheckResult:
    """Re-stamp a result with the canonical name derived from its function.

    Check functions historically hand-set ``CheckResult.name`` with ad-hoc
    strings that sometimes dropped a redundant category prefix
    (e.g. ``ci.workflow_exists`` instead of ``ci.ci_workflow_exists``). To
    keep ONE convention across SKIP / REDIRECT / exclude / display, every
    result is re-stamped here with :func:`_get_check_name` — the same value
    the skip/redirect filters key off. When the name cannot be inferred
    (function not named ``check_*``), the result's own name is kept.
    """
    canonical = _get_check_name(fn)
    if canonical is None or canonical == result.name:
        return result
    return result.model_copy(update={"name": canonical})


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


SKIP_FOR_MEMBER: frozenset[str] = frozenset(
    {
        "docs.gen_ref_pages",
        "docs.plugins",
        "docs.diataxis_nav",
        "docs.readme_badges",
        "deps.docs_group",
    }
)


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
        if (
            self.context == ProjectContext.WORKSPACE
            and check_name in SKIP_FOR_WORKSPACE
        ):
            return True
        return self.context == ProjectContext.MEMBER and check_name in SKIP_FOR_MEMBER

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
    ) -> list[Callable[[Path], CheckResult]]:
        """Apply context-aware skip and redirect filtering.

        Skip and redirect decisions key off the canonical
        ``category.fn_name`` name (:func:`_get_check_name`, the same
        convention used by ``SKIP_FOR_*`` / ``REDIRECT_FOR_*``). Exclusions
        are NOT handled here: they match against ``CheckResult.name`` after
        the check runs — but that name is now re-stamped with the SAME
        canonical value (see :func:`_stamp_canonical_name`), so excluding by
        the displayed name actually skips the check.
        """
        all_fns: list[Callable[[Path], CheckResult]] = []

        for _category, fns in checks_to_run.items():
            for fn in fns:
                check_name = _get_check_name(fn)
                if self._should_skip(check_name, _category):
                    continue
                if self._should_redirect(check_name):
                    all_fns.append(_redirect_to_root(fn, self.workspace_root))  # type: ignore[arg-type]
                else:
                    all_fns.append(fn)

        return all_fns

    def _apply_exclusions(
        self,
        results: list[CheckResult],
        exclusions: set[str],
    ) -> tuple[list[CheckResult], list[str]]:
        """Split run results into kept + excluded using the canonical name.

        Exclusion matching keys off ``CheckResult.name`` — which ``run`` has
        already re-stamped to the canonical :func:`_get_check_name` form, the
        same convention used by ``SKIP_FOR_*`` / ``REDIRECT_FOR_*`` and shown
        in the report. Excluding by the displayed name therefore actually
        skips the check. Excluded checks become auto-pass results carrying
        that same canonical name.
        """
        if not exclusions:
            return results, []

        kept: list[CheckResult] = []
        excluded_names: list[str] = []
        for result in results:
            if self._is_excluded(result.name, exclusions):
                kept.append(_make_excluded_result(result.name, result.category))
                excluded_names.append(result.name)
            else:
                kept.append(result)
        return kept, excluded_names

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
        all_fns = self._filter_checks(checks_to_run)

        with ThreadPoolExecutor(max_workers=8) as pool:
            raw_results = list(pool.map(lambda fn: fn(self.project_path), all_fns))

        # Single source of truth: re-stamp every result with the canonical
        # name (``_get_check_name``) so SKIP / REDIRECT / exclude / display
        # all key off the SAME string (AXM-2046).
        results = [
            _stamp_canonical_name(fn, result)
            for fn, result in zip(all_fns, raw_results, strict=True)
        ]

        results, excluded_names = self._apply_exclusions(results, exclusions)

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


def format_json(result: ProjectResult) -> dict[str, object]:
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


def format_agent(result: ProjectResult) -> dict[str, object]:
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
        "failures": [
            {
                "name": f.name,
                "message": f.message,
                "details": f.details,
                "fix": f.fix,
            }
            for f in result.failures
        ],
    }


def _format_agent_failure(failure: CheckResult) -> list[str]:
    """Render one failure as compact text: name, message, details, fix.

    Every detail line and the full multi-line fix are kept verbatim — the
    agent acts on them, so no information is dropped.
    """
    lines = [f"✗ {failure.name} — {failure.message}"]
    lines.extend(f"  · {detail}" for detail in failure.details)
    fix_lines = failure.fix.split("\n")
    lines.append(f"  → {fix_lines[0]}")
    lines.extend(f"    {line}" for line in fix_lines[1:])
    return lines


def format_agent_text(result: ProjectResult) -> str:
    """Agent-optimized text rendering of a check result.

    Compact companion to :func:`format_agent`: a one-line header with score,
    grade, context and pass/fail counts, then one block per failed check
    carrying its message, every detail and the full fix verbatim. Passed
    checks are summarized as a count (they carry no actionable remedy).

    The structured :func:`format_agent` dict remains the source of truth for
    programmatic consumers; this string is what the LLM reads.
    """
    passed = sum(1 for c in result.checks if c.passed)
    failures = result.failures
    context = result.context or "package"
    header = (
        f"init_check | {result.grade.value} {result.score}/100 | "
        f"{context} | {passed} ok · {len(failures)} fail"
    )
    if not failures:
        return f"{header}\nAll gold-standard checks passed."

    lines = [header, ""]
    for failure in failures:
        lines.extend(_format_agent_failure(failure))
    return "\n".join(lines)
