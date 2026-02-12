"""
axm-audit: Code auditing and quality rules for Python projects.

This package provides comprehensive project auditing capabilities including:
- Structure validation (files, directories)
- Quality checks (linting, type checking, complexity)
- Architecture analysis (circular imports, god classes, coupling)
- Best practices enforcement (docstrings, security patterns)

Example:
    >>> from axm_audit import audit_project
    >>> from pathlib import Path
    >>>
    >>> result = audit_project(Path("."))
    >>> print(f"Grade: {result.grade}")
    Grade: A
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
