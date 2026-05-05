"""Project Auditor — verifies projects against standards.

This module provides the public API for checking project compliance.
Rules execute in parallel via ThreadPoolExecutor for faster audits.

Rule discovery is automatic: every rule decorated with
``@register_rule`` is picked up via ``get_registry()``.
"""

from __future__ import annotations

import concurrent.futures
import contextvars
import logging
import traceback as _traceback
from pathlib import Path

from axm_audit.core.rules._helpers import (
    ASTCache,
    iter_workspace_packages,
    reset_ast_cache,
    set_ast_cache,
)
from axm_audit.core.rules.base import ProjectRule, get_registry
from axm_audit.models.results import (
    EXTRA_NONSCORED_CATEGORIES,
    SCORED_CATEGORIES,
    AuditResult,
    CheckResult,
    Severity,
)

logger = logging.getLogger(__name__)

# Valid audit categories: scored categories (from _CATEGORY_WEIGHTS) plus the
# non-scored extras (structure, tooling) that emit findings but are not
# weighted into quality_score.
VALID_CATEGORIES: frozenset[str] = SCORED_CATEGORIES | EXTRA_NONSCORED_CATEGORIES


def _ensure_registry_loaded() -> None:
    """Import all rule modules so ``@register_rule`` decorators fire."""
    import axm_audit.core.rules  # noqa: F401


def _build_all_rules() -> list[ProjectRule]:
    """Instantiate all rules from the auto-discovery registry."""
    _ensure_registry_loaded()
    registry = get_registry()

    rules: list[ProjectRule] = []
    for _cat, rule_classes in registry.items():
        for cls in rule_classes:
            rules.extend(cls.get_instances())
    return rules


def get_rules_for_category(
    category: str | None, quick: bool = False
) -> list[ProjectRule]:
    """Get rules for a specific category or all rules.

    Args:
        category: Filter to specific category, or None for all.
        quick: If True, only lint + type checks.

    Returns:
        List of rule instances to run.

    Raises:
        ValueError: If category is not valid.
    """
    _ensure_registry_loaded()

    if quick:
        from axm_audit.core.rules.quality import LintingRule, TypeCheckRule

        return [LintingRule(), TypeCheckRule()]

    # Validate category
    if category is not None and category not in VALID_CATEGORIES:
        raise ValueError(
            f"Invalid category: {category}. "
            f"Valid categories: {', '.join(sorted(VALID_CATEGORIES))}"
        )

    if not category:
        return _build_all_rules()

    registry = get_registry()
    rule_classes = registry.get(category, [])
    rules: list[ProjectRule] = []
    for cls in rule_classes:
        rules.extend(cls.get_instances())
    return rules


def _safe_check(rule: ProjectRule, project_path: Path) -> CheckResult:
    """Run a single rule with exception handling.

    If the rule raises, returns a failed CheckResult rather than crashing.
    Injects ``rule.category`` into the returned CheckResult.
    Includes traceback in ``details`` on failure for debugging.
    """
    try:
        result = rule.check(project_path)
        result.category = rule.category
        return result
    except Exception as exc:  # noqa: BLE001
        tb = _traceback.format_exc()[-500:]
        logger.warning("Rule %s raised: %s", rule.rule_id, exc, exc_info=True)
        return CheckResult(
            rule_id=rule.rule_id,
            passed=False,
            message=f"Rule crashed: {exc}",
            severity=Severity.ERROR,
            fix_hint="Check rule configuration and dependencies",
            category=rule.category,
            details={"traceback": tb},
        )


def audit_project(
    project_path: Path,
    category: str | None = None,
    quick: bool = False,
) -> AuditResult:
    """Audit a project against Python 2026 standards.

    Rules execute in parallel via ThreadPoolExecutor for speed.
    Each rule is isolated — one failure does not prevent others.
    An ``ASTCache`` is shared across rules to avoid redundant parsing.

    Args:
        project_path: Root directory of the project to audit.
        category: Optional category filter.
        quick: If True, run only lint + type checks.

    Returns:
        AuditResult containing all check results.

    Raises:
        FileNotFoundError: If project_path does not exist.
    """
    if not project_path.exists():
        raise FileNotFoundError(f"Project path does not exist: {project_path}")

    workspace_packages = iter_workspace_packages(project_path)
    if workspace_packages:
        return _audit_workspace(
            project_path, workspace_packages, category=category, quick=quick
        )

    rules = get_rules_for_category(category, quick)

    cache = ASTCache()
    token = set_ast_cache(cache)
    try:
        with concurrent.futures.ThreadPoolExecutor() as pool:
            futures = [
                pool.submit(
                    contextvars.copy_context().run, _safe_check, rule, project_path
                )
                for rule in rules
            ]
            checks = [f.result() for f in futures]
    finally:
        reset_ast_cache(token)

    return AuditResult(project_path=str(project_path), checks=checks)


def _audit_workspace(
    workspace_path: Path,
    packages: list[Path],
    *,
    category: str | None,
    quick: bool,
) -> AuditResult:
    """Audit each package in a multi-package workspace and merge results.

    Each package is audited independently (as if it were a standalone
    project) and per-package CheckResults are merged by ``rule_id``
    using a worst-of-N policy: any failure fails the merged result, and
    score-bearing rules report the minimum score across packages. Text
    blocks are concatenated with a per-package header so consumers can
    disambiguate which package emitted which violation.
    """
    per_package: list[tuple[str, list[CheckResult]]] = []
    for pkg in packages:
        sub = audit_project(pkg, category=category, quick=quick)
        per_package.append((pkg.name, list(sub.checks)))

    merged: dict[str, CheckResult] = {}
    order: list[str] = []
    for pkg_name, checks in per_package:
        for check in checks:
            if check.rule_id not in merged:
                order.append(check.rule_id)
                merged[check.rule_id] = _prefix_check(check, pkg_name)
                continue
            merged[check.rule_id] = _merge_check(merged[check.rule_id], check, pkg_name)

    return AuditResult(
        project_path=str(workspace_path),
        checks=[merged[r] for r in order],
    )


def _prefix_check(check: CheckResult, pkg_name: str) -> CheckResult:
    """Return a copy of *check* with *pkg_name* prefixed into text/details."""
    text = f"[{pkg_name}]\n{check.text}" if check.text else None
    details = dict(check.details) if check.details else {}
    if details:
        details["package"] = pkg_name
    message = f"{pkg_name}: {check.message}" if check.message else check.message
    return check.model_copy(
        update={"text": text, "details": details or None, "message": message}
    )


def _merge_check(
    existing: CheckResult, incoming: CheckResult, pkg_name: str
) -> CheckResult:
    """Merge two CheckResults for the same rule_id (worst-of-N policy)."""
    incoming_prefixed = _prefix_check(incoming, pkg_name)
    return existing.model_copy(
        update={
            "passed": existing.passed and incoming_prefixed.passed,
            "text": _merge_text(existing.text, incoming_prefixed.text),
            "details": _merge_details(existing.details, incoming_prefixed.details),
            "severity": _max_severity(existing.severity, incoming_prefixed.severity),
            "message": existing.message,
            "score": _merge_score(existing.score, incoming_prefixed.score),
        }
    )


def _merge_score(a: int | None, b: int | None) -> int | None:
    """Worst-of-N score: None if both None, else min of set values."""
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)


def _merge_text(a: str | None, b: str | None) -> str | None:
    """Join non-empty texts with newline; None if both empty."""
    parts = [t for t in (a, b) if t]
    return "\n".join(parts) if parts else None


def _merge_details(
    a: dict[str, object] | None, b: dict[str, object] | None
) -> dict[str, object] | None:
    """Shallow merge; incoming overrides existing. None if empty."""
    merged: dict[str, object] = {}
    if a:
        merged.update(a)
    if b:
        merged.update(b)
    return merged or None


_SEVERITY_RANK = {Severity.INFO: 0, Severity.WARNING: 1, Severity.ERROR: 2}


def _max_severity(a: Severity, b: Severity) -> Severity:
    """Return the more severe of two ``Severity`` values."""
    return a if _SEVERITY_RANK[a] >= _SEVERITY_RANK[b] else b
