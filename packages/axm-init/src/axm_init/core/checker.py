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
from axm_init.core.framework import (
    Framework,
    detect_framework,
    resolve_frameworks,
)
from axm_init.models.check import CheckResult, ProjectResult

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

__all__ = [
    "ALL_CHECKS",
    "REDIRECT_BY_CONTEXT",
    "SKIP_BY_CONTEXT",
    "VALID_CATEGORIES",
    "CheckEngine",
    "format_agent",
    "format_agent_text",
    "format_json",
    "format_report",
    "get_check_name",
    "resolve_exit_code",
    "stamp_canonical_name",
    "validate_context_tables",
]


# Sub-packages of ``axm_init.checks`` that hold a non-Python framework's
# checks. They are skipped by the default (Python) discovery scan and picked up
# only when the project's framework selects them.
_FRAMEWORK_CHECK_PACKAGES: frozenset[str] = frozenset({"node", "svelte", "react"})


def _collect_check_fns(module: object) -> list[Callable[[Path], CheckResult]]:
    """Return the public ``check_*`` functions defined on *module*."""
    import inspect

    return [
        obj
        for name, obj in inspect.getmembers(module, inspect.isfunction)
        if name.startswith("check_") and not name.startswith("_")
    ]


def _discover_checks(
    package: object = _checks_pkg,
    *,
    prefix: str = "axm_init.checks",
    skip_packages: frozenset[str] = _FRAMEWORK_CHECK_PACKAGES,
) -> dict[str, list[Callable[[Path], CheckResult]]]:
    """Auto-discover ``check_*`` functions from the modules of *package*.

    Scans every public module (skipping private ``_``-prefixed modules and the
    framework sub-packages in *skip_packages*) and collects all public
    ``check_*`` functions. The module name becomes the category key.

    Args:
        package: The package object to scan (defaults to ``axm_init.checks``).
        prefix: Import prefix for the package's modules.
        skip_packages: Sub-package names to skip (the per-framework check sets).
    """
    registry: dict[str, list[Callable[[Path], CheckResult]]] = {}
    for info in pkgutil.iter_modules(package.__path__):  # type: ignore[attr-defined]
        if info.name.startswith("_") or info.name in skip_packages:
            continue
        mod = importlib.import_module(f"{prefix}.{info.name}")
        fns = _collect_check_fns(mod)
        if fns:
            registry[info.name] = fns
    return registry


def _discover_framework_checks(
    framework: Framework,
) -> dict[str, list[Callable[[Path], CheckResult]]]:
    """Discover the gold-standard checks for a single non-Python *framework*.

    Looks for a ``axm_init.checks.<framework>`` sub-package. Missing packages
    (a framework with no delta checks yet) yield an empty registry rather than
    an error, so a UI framework can be added incrementally.
    """
    import importlib

    pkg_name = f"axm_init.checks.{framework.value}"
    try:
        pkg = importlib.import_module(pkg_name)
    except ModuleNotFoundError:
        return {}
    return _discover_checks(pkg, prefix=pkg_name, skip_packages=frozenset())


def _build_checks_by_framework() -> dict[
    Framework, dict[str, list[Callable[[Path], CheckResult]]]
]:
    """Build the per-framework check registry, resolving the node→UI chain.

    Python uses its own check set. Each non-Python framework merges the check
    sets of its resolution chain (e.g. svelte = node ⊕ svelte), so the shared
    node checks run for every UI framework without duplication.
    """
    per_fw: dict[Framework, dict[str, list[Callable[[Path], CheckResult]]]] = {
        Framework.PYTHON: ALL_CHECKS,
    }
    for framework in (Framework.NODE, Framework.SVELTE, Framework.REACT):
        merged: dict[str, list[Callable[[Path], CheckResult]]] = {}
        for fw in resolve_frameworks(framework):
            for category, fns in _discover_framework_checks(fw).items():
                merged.setdefault(category, []).extend(fns)
        per_fw[framework] = merged
    return per_fw


def get_check_name(fn: Callable[[Path], CheckResult]) -> str | None:
    """Derive the canonical check name from the function's module + name.

    This is THE single source of truth for check naming. The convention is
    ``category.function_name_without_check_`` (the module name is the
    category). The same string is used by the context tables
    ``SKIP_BY_CONTEXT`` / ``REDIRECT_BY_CONTEXT``
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


def stamp_canonical_name(
    fn: Callable[[Path], CheckResult],
    result: CheckResult,
) -> CheckResult:
    """Re-stamp a result with the canonical name derived from its function.

    Check functions historically hand-set ``CheckResult.name`` with ad-hoc
    strings that sometimes dropped a redundant category prefix
    (e.g. ``ci.workflow_exists`` instead of ``ci.ci_workflow_exists``). To
    keep ONE convention across SKIP / REDIRECT / exclude / display, every
    result is re-stamped here with :func:`get_check_name` — the same value
    the skip/redirect filters key off. When the name cannot be inferred
    (function not named ``check_*``), the result's own name is kept.
    """
    canonical = get_check_name(fn)
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


# Registry: category -> list of check functions (Python gold standard).
ALL_CHECKS: dict[str, list[Callable[[Path], CheckResult]]] = _discover_checks()

# Per-framework gold-standard check sets, keyed by framework. Each UI framework
# merges the node base layer with its own delta (svelte = node ⊕ svelte, …).
CHECKS_BY_FRAMEWORK: dict[Framework, dict[str, list[Callable[[Path], CheckResult]]]] = (
    _build_checks_by_framework()
)

# Union of every category across every framework — used only for the
# error-message hint; per-framework validation happens in ``run()``.
VALID_CATEGORIES = {
    category for registry in CHECKS_BY_FRAMEWORK.values() for category in registry
}


# --- Context-keyed skip / redirect tables --------------------------------
#
# ONE table per decision, keyed by ProjectContext: a fourth context is a new
# row, never a new branch in the engine. Every id is checked against the
# discovered check ids by :func:`validate_context_tables`, called from the
# engine constructor — a typo is a hard error, not a silently inert skip.


def _known_check_ids() -> frozenset[str]:
    """Return every canonical check id declared by the discovery registry."""
    return frozenset(
        name
        for fns in ALL_CHECKS.values()
        for fn in fns
        if (name := get_check_name(fn)) is not None
    )


def _category_check_ids(category: str) -> frozenset[str]:
    """Return the canonical check ids registered under *category*."""
    return frozenset(
        name
        for fn in ALL_CHECKS.get(category, [])
        if (name := get_check_name(fn)) is not None
    )


# Checks that only make sense on a workspace root: every other context skips
# the whole ``workspace`` category.
_WORKSPACE_ONLY_CHECKS: frozenset[str] = _category_check_ids("workspace")

# Package-level concerns a workspace root does not carry.
_WORKSPACE_ROOT_SKIPS: frozenset[str] = frozenset(
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

# Docs/deps concerns owned by the workspace root, not by each of its members.
_MEMBER_SKIPS: frozenset[str] = frozenset(
    {
        "docs.gen_ref_pages",
        "docs.plugins",
        "docs.diataxis_nav",
        "docs.readme_badges",
        "deps.docs_group",
    }
)

# CI/tooling checks a member delegates to its workspace root.
_MEMBER_REDIRECTS: frozenset[str] = frozenset(
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

# A paper's own invariants: meaningless in every non-paper context.
_PAPER_CHECKS: frozenset[str] = _category_check_ids("paper")

# An experiment folder's own form invariants: meaningless everywhere else,
# so every NON-experiment context skips the whole ``experiment`` category.
# Derived from the registry, never hand-listed.
_EXPERIMENT_CHECKS: frozenset[str] = _category_check_ids("experiment")

# Every Python-packaging check id — i.e. everything that is neither a paper
# nor an experiment check. Derived from the registry instead of hand-listed,
# so a packaging check added later is skipped on a paper the day it lands.
_PACKAGING_CHECKS: frozenset[str] = (
    _known_check_ids() - _PAPER_CHECKS - _EXPERIMENT_CHECKS
)

# Checks skipped entirely, per detected project context.
SKIP_BY_CONTEXT: dict[ProjectContext, frozenset[str]] = {
    ProjectContext.STANDALONE: (
        _WORKSPACE_ONLY_CHECKS | _PAPER_CHECKS | _EXPERIMENT_CHECKS
    ),
    ProjectContext.WORKSPACE: (
        _WORKSPACE_ROOT_SKIPS | _PAPER_CHECKS | _EXPERIMENT_CHECKS
    ),
    ProjectContext.MEMBER: (
        _WORKSPACE_ONLY_CHECKS | _MEMBER_SKIPS | _PAPER_CHECKS | _EXPERIMENT_CHECKS
    ),
    # A paper is not a Python distribution: the whole packaging rulebook is
    # out, only the paper's own invariants are graded — and an experiment's
    # form checks belong to the experiment folders nested under it, not to
    # the paper root.
    ProjectContext.PAPER: _PACKAGING_CHECKS | _EXPERIMENT_CHECKS,
    # An experiment folder is not a Python distribution either: it holds a
    # manifest, not a pyproject.toml / src/ / py.typed / test pyramid /
    # mkdocs.yml. The whole packaging rulebook is out, and so are the paper
    # invariants (they belong to the paper root above it) — only the two
    # experiment FORM checks are graded. Both operands come from the
    # registry-derived sets, so a check added or renamed later is routed (or
    # rejected by ``validate_context_tables``) instead of drifting.
    ProjectContext.EXPERIMENT: _PACKAGING_CHECKS | _PAPER_CHECKS,
}

# Checks run against the workspace root instead, per detected context.
REDIRECT_BY_CONTEXT: dict[ProjectContext, frozenset[str]] = {
    ProjectContext.STANDALONE: frozenset(),
    ProjectContext.WORKSPACE: frozenset(),
    ProjectContext.MEMBER: _MEMBER_REDIRECTS,
    # Like a member, a paper delegates CI/tooling to its workspace root.
    ProjectContext.PAPER: _MEMBER_REDIRECTS,
    # Nothing to redirect: every redirectable id is a packaging check, and
    # the experiment context skips the packaging rulebook outright.
    ProjectContext.EXPERIMENT: frozenset(),
}


def validate_context_tables() -> None:
    """Check every context-table id against the discovered check registry.

    Raises:
        ValueError: if a table holds an id no registered check declares —
            the message names every offending id.
    """
    known = _known_check_ids()
    unknown = sorted(
        check_id
        for table in (SKIP_BY_CONTEXT, REDIRECT_BY_CONTEXT)
        for ids in table.values()
        for check_id in ids
        if check_id not in known
    )
    if unknown:
        listed = ", ".join(repr(check_id) for check_id in unknown)
        msg = f"Unknown check id(s) in the context tables: {listed}"
        raise ValueError(msg)


class CheckEngine:
    """Orchestrates project checks and produces results."""

    def __init__(
        self,
        project_path: Path,
        *,
        category: str | None = None,
        framework: Framework | str | None = None,
    ) -> None:
        validate_context_tables()
        self.project_path = project_path.resolve()
        self.category = category
        self.framework = (
            detect_framework(self.project_path)
            if framework is None
            else Framework(framework)
        )
        self.context = detect_context(self.project_path)
        self.workspace_root = find_workspace_root(self.project_path)

    def _is_excluded(self, check_name: str, exclusions: set[str]) -> bool:
        """Check if a check name matches any exclusion prefix."""
        return any(check_name.startswith(prefix) for prefix in exclusions)

    def _should_skip(self, check_name: str | None) -> bool:
        """Return True if the check should be skipped for context reasons."""
        return check_name in SKIP_BY_CONTEXT.get(self.context, frozenset())

    def _should_redirect(self, check_name: str | None) -> bool:
        """Return True if the check should be redirected to workspace root."""
        return (
            check_name in REDIRECT_BY_CONTEXT.get(self.context, frozenset())
            and self.workspace_root is not None
        )

    def _filter_checks(
        self,
        checks_to_run: dict[str, list[Callable[[Path], CheckResult]]],
    ) -> list[Callable[[Path], CheckResult]]:
        """Apply context-aware skip and redirect filtering.

        Skip and redirect decisions key off the canonical
        ``category.fn_name`` name (:func:`get_check_name`, the same
        convention used by the context tables). Exclusions
        are NOT handled here: they match against ``CheckResult.name`` after
        the check runs — but that name is now re-stamped with the SAME
        canonical value (see :func:`stamp_canonical_name`), so excluding by
        the displayed name actually skips the check.
        """
        all_fns: list[Callable[[Path], CheckResult]] = []

        for fns in checks_to_run.values():
            for fn in fns:
                check_name = get_check_name(fn)
                if self._should_skip(check_name):
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
        already re-stamped to the canonical :func:`get_check_name` form, the
        same convention used by the context tables and shown
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
        """Run all checks (or filtered by category) for the project's framework."""
        registry = CHECKS_BY_FRAMEWORK.get(self.framework, ALL_CHECKS)
        if self.category:
            if self.category not in registry:
                valid = ", ".join(sorted(registry.keys()))
                msg = (
                    f"Unknown category '{self.category}' for framework "
                    f"'{self.framework.value}'. Valid: {valid}"
                )
                raise ValueError(msg)
            checks_to_run = {self.category: registry[self.category]}
        else:
            checks_to_run = registry

        exclusions = load_exclusions(self.project_path)
        all_fns = self._filter_checks(checks_to_run)

        with ThreadPoolExecutor(max_workers=8) as pool:
            raw_results = list(pool.map(lambda fn: fn(self.project_path), all_fns))

        # Single source of truth: re-stamp every result with the canonical
        # name (``get_check_name``) so SKIP / REDIRECT / exclude / display
        # all key off the SAME string (AXM-2046).
        results = [
            stamp_canonical_name(fn, result)
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

    # Score — a not-applicable run (no weighted checks scored in this
    # context, e.g. `check --category workspace` on a standalone project)
    # renders an N/A line, NOT a numeric 0/100 Grade F.
    if result.not_applicable:
        lines.append(
            "  Category not applicable (N/A) — no checks scored in this context"
        )
    else:
        grade_emoji = {"A": "🏆", "B": "✅", "C": "⚠️", "D": "🔧", "F": "❌"}
        emoji = grade_emoji.get(result.grade.value, "")
        lines.append(
            f"  Score: {result.score}/100 — Grade {result.grade.value} {emoji}"
        )
    lines.append("")

    # Failures
    if result.failures:
        lines.extend(_format_failures(result.failures))

    return "\n".join(lines)


def resolve_exit_code(result: ProjectResult) -> int:
    """Resolve the CLI process exit code for a check *result*.

    A not-applicable verdict (no weighted checks ran for this context — e.g.
    a category that does not apply to the project) is a skip/success and
    exits ``0``. An applicable run exits ``0`` only on a perfect score,
    otherwise ``1`` — so a real 0/100 Grade F still fails the process.
    """
    if result.not_applicable:
        return 0
    return 0 if result.score >= 100 else 1


def format_json(result: ProjectResult) -> dict[str, object]:
    """Format check result as JSON-serializable dict."""
    return {
        "project": str(result.project_path),
        "score": None if result.not_applicable else result.score,
        "grade": None if result.not_applicable else result.grade.value,
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
        "score": None if result.not_applicable else result.score,
        "grade": None if result.not_applicable else result.grade.value,
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
    # A not-applicable run (no weighted checks scored in this context) renders
    # an N/A marker, NOT a numeric 0/100 Grade F — else the LLM reads a real
    # failure where a dimension simply does not apply.
    verdict = (
        "N/A" if result.not_applicable else f"{result.grade.value} {result.score}/100"
    )
    header = f"init_check | {verdict} | {context} | {passed} ok · {len(failures)} fail"
    if not failures:
        return f"{header}\nAll gold-standard checks passed."

    lines = [header, ""]
    for failure in failures:
        lines.extend(_format_agent_failure(failure))
    return "\n".join(lines)
