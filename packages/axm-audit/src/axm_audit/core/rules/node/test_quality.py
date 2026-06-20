"""Node test-quality rules — DECLARED but NOT YET IMPLEMENTED.

These are the rules with no off-the-shelf node tool: the AXM-specific test
hygiene invariants (mirror, pyramid level, tautology, duplicate tests). In
Python they run on axm-ast's tree-sitter AST. Porting them to TS/JS requires a
TypeScript AST on the Python side — either extending axm-ast with a
tree-sitter-typescript grammar, or a dedicated node AST helper (ts-morph) invoked
as a subprocess. That decision is deferred.

Until then they are registered as **explicit placeholders** so the node coverage
is honest: each returns a neutral, non-scored ``CheckResult`` that says
NOT_IMPLEMENTED and names the dependency (TS AST). They never emit a false green
(``passed=True`` with a real 100 score) — they are reported as INFO/skipped with
``score=None`` so they don't inflate the quality score, and a consumer can see
exactly which dimensions still await the AST work.
"""

from __future__ import annotations

from pathlib import Path

from axm_audit.core.framework import Framework
from axm_audit.core.rules.base import ProjectRule, register_rule
from axm_audit.models.results import CheckResult, Severity

__all__ = [
    "NodeTestDuplicateRule",
    "NodeTestMirrorRule",
    "NodeTestPyramidRule",
    "NodeTestTautologyRule",
]

# Why these can't be ported by shelling out to an existing tool, and what they
# need — surfaced verbatim in every placeholder result.
_NEEDS_TS_AST = (
    "NOT_IMPLEMENTED: requires a TypeScript AST on the Python side "
    "(extend axm-ast with tree-sitter-typescript, or a ts-morph subprocess). "
    "No off-the-shelf node tool covers this AXM-specific invariant."
)


class _NotImplementedTSRule(ProjectRule):
    """Base for a declared-but-unimplemented node test-quality rule.

    Emits a neutral, non-scored result (``score=None``, INFO) that names the
    missing dependency. Never a false green; never inflates the quality score.
    """

    def check(self, project_path: Path) -> CheckResult:
        """Return the NOT_IMPLEMENTED placeholder result for this rule."""
        return CheckResult(
            rule_id=self.rule_id,
            passed=True,
            message=f"{self.rule_id}: not implemented for node yet",
            severity=Severity.INFO,
            score=None,
            details={"status": "not_implemented", "needs": "ts_ast"},
            fix_hint=_NEEDS_TS_AST,
        )


@register_rule("test_quality", framework=Framework.NODE)
class NodeTestMirrorRule(_NotImplementedTSRule):
    """Every source module has a matching test (Python: ``MirrorRule``)."""

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "NODE_TEST_MIRROR"


@register_rule("test_quality", framework=Framework.NODE)
class NodeTestPyramidRule(_NotImplementedTSRule):
    """Tests sit at the right pyramid level (Python: pyramid_level)."""

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "NODE_TEST_PYRAMID_LEVEL"


@register_rule("test_quality", framework=Framework.NODE)
class NodeTestTautologyRule(_NotImplementedTSRule):
    """No tautological assertions (Python: tautology)."""

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "NODE_TEST_TAUTOLOGY"


@register_rule("test_quality", framework=Framework.NODE)
class NodeTestDuplicateRule(_NotImplementedTSRule):
    """No duplicate test bodies (Python: duplicate_tests)."""

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "NODE_TEST_DUPLICATE"
