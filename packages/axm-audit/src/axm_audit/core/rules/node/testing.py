"""Node testing rule — the Vitest pendant of :class:`TestCoverageRule`.

Ports the intent of ``QUALITY_COVERAGE`` / the test-suite-runs invariant to the
Node ecosystem via Vitest's JSON reporter.

False-green guard (from the research): a green ``vitest run`` proves nothing if
zero tests ran (``passWithNoTests``). We assert ``numTotalTests > 0`` AND all
passed; an empty suite fails this rule.
"""

from __future__ import annotations

from pathlib import Path

from axm_audit.core.framework import Framework
from axm_audit.core.rules.base import register_rule
from axm_audit.core.rules.node._base import NodeToolRule
from axm_audit.models.results import CheckResult, Severity

__all__ = ["NodeTestRule"]


def _test_counts(parsed: object) -> tuple[int, int, int]:
    """Return (total, passed, failed) from Vitest's JSON report."""
    if not isinstance(parsed, dict):
        return (0, 0, 0)

    def _int(key: str) -> int:
        value = parsed.get(key, 0)
        return value if isinstance(value, int) else 0

    return (_int("numTotalTests"), _int("numPassedTests"), _int("numFailedTests"))


@register_rule("testing", framework=Framework.NODE)
class NodeTestRule(NodeToolRule):
    """Run Vitest and require a non-empty, fully-passing suite.

    Mirrors the Python testing invariant: a green run with zero tests is NOT a
    pass (guards against ``passWithNoTests``). Score is the pass ratio times
    100, forced to 0 when no tests ran.
    """

    binary = "vitest"
    install_hint = "Install Vitest: npm install -D vitest"

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "QUALITY_TESTING"

    @property
    def args(self) -> list[str]:
        """Run the suite once with the JSON reporter (no watch)."""
        return ["run", "--reporter=json"]

    @property
    def findings_returncodes(self) -> frozenset[int]:
        """Vitest exits 1 when tests fail — a finding we score, not a crash."""
        return frozenset({1})

    def score_output(self, parsed: object, project_path: Path) -> CheckResult:
        """Score by pass ratio; an empty suite is a hard fail (false-green guard)."""
        total, passed_count, failed = _test_counts(parsed)
        if total == 0:
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="No tests ran (numTotalTests == 0)",
                severity=Severity.ERROR,
                score=0,
                details={"total": 0},
                fix_hint="Add tests — an empty suite never passes this gate.",
            )
        score = round(passed_count / total * 100)
        passed = failed == 0
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Tests: {passed_count}/{total} passed",
            severity=Severity.ERROR if not passed else Severity.INFO,
            score=score,
            details={"total": total, "passed": passed_count, "failed": failed},
            fix_hint="Fix the failing tests above" if failed else None,
        )
