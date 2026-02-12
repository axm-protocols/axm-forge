"""
axm-audit: Code auditing and quality rules for Python projects.

This package provides comprehensive project auditing capabilities including:
- Structure validation (files, directories)
- Quality checks (linting, type checking, complexity)
- Security analysis (Bandit integration, secrets detection)
- Dependency scanning (pip-audit, deptry)
- Test coverage enforcement (pytest-cov)
- Architecture analysis (circular imports, god classes, coupling)
- Best practices enforcement (docstrings, security patterns)

Example:
    >>> from axm_audit import audit_project
    >>> from pathlib import Path
    >>>
    >>> result = audit_project(Path("."))
    >>> print(f"Score: {result.quality_score}/100 — Grade {result.grade}")
    Score: 95.0/100 — Grade A
"""

from axm_audit.core.auditor import audit_project, get_rules_for_category
from axm_audit.models import AuditResult, CheckResult, Severity

__version__ = "1.0.0"

__all__ = [
    "AuditResult",
    "CheckResult",
    "Severity",
    "audit_project",
    "get_rules_for_category",
]
