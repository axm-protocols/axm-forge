"""Project Auditor — verifies projects against standards.

This module provides the public API for checking project compliance.
"""

from pathlib import Path

from axm_audit.core.rules import (
    BareExceptRule,
    CircularImportRule,
    ComplexityRule,
    CouplingMetricRule,
    DependencyAuditRule,
    DependencyHygieneRule,
    DocstringCoverageRule,
    GodClassRule,
    LintingRule,
    PyprojectCompletenessRule,
    SecurityPatternRule,
    SecurityRule,
    TestCoverageRule,
    ToolAvailabilityRule,
    TypeCheckRule,
)
from axm_audit.core.rules.base import ProjectRule
from axm_audit.models.results import AuditResult

# Valid audit categories
VALID_CATEGORIES = {
    "structure",
    "quality",
    "architecture",
    "practice",
    "security",
    "dependencies",
    "testing",
    "tooling",
}

# Rule categories for filtering
RULES_BY_CATEGORY: dict[str, list[type[ProjectRule]]] = {
    "structure": [PyprojectCompletenessRule],
    "quality": [LintingRule, TypeCheckRule, ComplexityRule],
    "architecture": [CircularImportRule, GodClassRule, CouplingMetricRule],
    "practice": [DocstringCoverageRule, BareExceptRule, SecurityPatternRule],
    "security": [SecurityRule],
    "dependencies": [DependencyAuditRule, DependencyHygieneRule],
    "testing": [TestCoverageRule],
    "tooling": [ToolAvailabilityRule],
}


def _get_tooling_rules() -> list[ProjectRule]:
    """Get tooling availability rules with required parameters.

    Returns:
        List of instantiated tooling rules.
    """
    return [
        ToolAvailabilityRule(tool_name="ruff"),
        ToolAvailabilityRule(tool_name="mypy"),
        ToolAvailabilityRule(tool_name="uv"),
    ]


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
    if quick:
        return [LintingRule(), TypeCheckRule()]

    # Validate category
    if category is not None and category not in VALID_CATEGORIES:
        raise ValueError(
            f"Invalid category: {category}. "
            f"Valid categories: {', '.join(sorted(VALID_CATEGORIES))}"
        )

    if category:
        if category == "tooling":
            return _get_tooling_rules()
        rule_classes = RULES_BY_CATEGORY.get(category, [])
        return [cls() for cls in rule_classes]

    # All rules
    return [
        PyprojectCompletenessRule(),
        LintingRule(),
        TypeCheckRule(),
        ComplexityRule(),
        SecurityRule(),
        DependencyAuditRule(),
        DependencyHygieneRule(),
        TestCoverageRule(),
        CircularImportRule(),
        GodClassRule(),
        CouplingMetricRule(),
        DocstringCoverageRule(),
        BareExceptRule(),
        SecurityPatternRule(),
        *_get_tooling_rules(),
    ]


def audit_project(
    project_path: Path,
    category: str | None = None,
    quick: bool = False,
) -> AuditResult:
    """Audit a project against Python 2026 standards.

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
    checks = [rule.check(project_path) for rule in rules]
    return AuditResult(checks=checks)
