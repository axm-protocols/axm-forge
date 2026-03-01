"""Project Auditor — verifies projects against standards.

This module provides the public API for checking project compliance.
Rules execute in parallel via ThreadPoolExecutor for faster audits.

Rule discovery is automatic: every rule decorated with
``@register_rule`` is picked up via ``get_registry()``.
"""

from __future__ import annotations

import concurrent.futures
import logging
import traceback as _traceback
from pathlib import Path

from axm_audit.core.rules._helpers import ASTCache, set_ast_cache
from axm_audit.core.rules.base import ProjectRule, get_registry
from axm_audit.models.results import AuditResult, CheckResult, Severity

logger = logging.getLogger(__name__)

# Valid audit categories — aligned with scoring weights
VALID_CATEGORIES = {
    "lint",
    "type",
    "complexity",
    "security",
    "deps",
    "testing",
    "architecture",
    "practices",
    "structure",
    "tooling",
}


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

    rules = get_rules_for_category(category, quick)

    cache = ASTCache()
    set_ast_cache(cache)
    try:
        with concurrent.futures.ThreadPoolExecutor() as pool:
            checks = list(pool.map(lambda r: _safe_check(r, project_path), rules))
    finally:
        set_ast_cache(None)

    return AuditResult(project_path=str(project_path), checks=checks)
