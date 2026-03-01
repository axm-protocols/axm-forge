"""Rules subpackage — modular project rule implementations."""

from axm_audit.core.rules.architecture import (
    CircularImportRule,
    CouplingMetricRule,
    GodClassRule,
)
from axm_audit.core.rules.base import ProjectRule
from axm_audit.core.rules.complexity import ComplexityRule
from axm_audit.core.rules.coverage import TestCoverageRule
from axm_audit.core.rules.dependencies import (
    DependencyAuditRule,
    DependencyHygieneRule,
)
from axm_audit.core.rules.practices import (
    BareExceptRule,
    BlockingIORule,
    DocstringCoverageRule,
    LoggingPresenceRule,
    SecurityPatternRule,
)
from axm_audit.core.rules.quality import (
    FormattingRule,
    LintingRule,
    TypeCheckRule,
)
from axm_audit.core.rules.security import SecurityRule
from axm_audit.core.rules.structure import PyprojectCompletenessRule
from axm_audit.core.rules.tooling import ToolAvailabilityRule

__all__ = [
    "BareExceptRule",
    "BlockingIORule",
    "CircularImportRule",
    "ComplexityRule",
    "CouplingMetricRule",
    "DependencyAuditRule",
    "DependencyHygieneRule",
    "DocstringCoverageRule",
    "FormattingRule",
    "GodClassRule",
    "LintingRule",
    "LoggingPresenceRule",
    "ProjectRule",
    "PyprojectCompletenessRule",
    "SecurityPatternRule",
    "SecurityRule",
    "TestCoverageRule",
    "ToolAvailabilityRule",
    "TypeCheckRule",
]
