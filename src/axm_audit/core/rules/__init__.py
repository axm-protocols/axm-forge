"""Rules subpackage — modular project rule implementations."""

from axm_audit.core.rules.architecture import (
    CircularImportRule,
    CouplingMetricRule,
    GodClassRule,
)
from axm_audit.core.rules.base import ProjectRule
from axm_audit.core.rules.practices import (
    BareExceptRule,
    DocstringCoverageRule,
    SecurityPatternRule,
)
from axm_audit.core.rules.quality import ComplexityRule, LintingRule, TypeCheckRule
from axm_audit.core.rules.structure import DirectoryExistsRule, FileExistsRule
from axm_audit.core.rules.tooling import ToolAvailabilityRule

__all__ = [
    "BareExceptRule",
    "CircularImportRule",
    "ComplexityRule",
    "CouplingMetricRule",
    "DirectoryExistsRule",
    "DocstringCoverageRule",
    "FileExistsRule",
    "GodClassRule",
    "LintingRule",
    "ProjectRule",
    "SecurityPatternRule",
    "ToolAvailabilityRule",
    "TypeCheckRule",
]
