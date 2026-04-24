"""Rules subpackage — modular project rule implementations."""

from axm_audit.core.rules.architecture import (
    CircularImportRule,
    CouplingMetricRule,
    GodClassRule,
)
from axm_audit.core.rules.base import ProjectRule, get_registry, register_rule
from axm_audit.core.rules.complexity import ComplexityRule
from axm_audit.core.rules.coverage import TestCoverageRule
from axm_audit.core.rules.dead_code import DeadCodeRule
from axm_audit.core.rules.dependencies import (
    DependencyAuditRule,
    DependencyHygieneRule,
)
from axm_audit.core.rules.duplication import DuplicationRule
from axm_audit.core.rules.practices import (
    BareExceptRule,
    BlockingIORule,
    DocstringCoverageRule,
    SecurityPatternRule,
    TestMirrorRule,
)
from axm_audit.core.rules.quality import (
    DiffSizeRule,
    FormattingRule,
    LintingRule,
    TypeCheckRule,
)
from axm_audit.core.rules.security import SecurityRule
from axm_audit.core.rules.structure import PyprojectCompletenessRule
from axm_audit.core.rules.test_quality import (  # noqa: F401  (side-effect: registration)
    duplicate_tests as _test_quality_duplicate_tests,
)
from axm_audit.core.rules.test_quality import (
    private_imports as _test_quality_private_imports,
)
from axm_audit.core.rules.test_quality import (
    pyramid_level as _test_quality_pyramid_level,
)
from axm_audit.core.rules.test_quality import (
    tautology as _test_quality_tautology,
)
from axm_audit.core.rules.tooling import ToolAvailabilityRule

__all__ = [
    "BareExceptRule",
    "BlockingIORule",
    "CircularImportRule",
    "ComplexityRule",
    "CouplingMetricRule",
    "DeadCodeRule",
    "DependencyAuditRule",
    "DependencyHygieneRule",
    "DiffSizeRule",
    "DocstringCoverageRule",
    "DuplicationRule",
    "FormattingRule",
    "GodClassRule",
    "LintingRule",
    "ProjectRule",
    "PyprojectCompletenessRule",
    "SecurityPatternRule",
    "SecurityRule",
    "TestCoverageRule",
    "TestMirrorRule",
    "ToolAvailabilityRule",
    "TypeCheckRule",
    "get_registry",
    "register_rule",
]
