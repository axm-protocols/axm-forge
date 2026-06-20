"""Node type-check rule — the ``tsc`` pendant of :class:`TypeCheckRule`.

Ports the intent of ``QUALITY_TYPE`` (static type errors) to TypeScript via
``tsc --noEmit``. ``tsc`` has no JSON reporter, so we count ``error TS`` lines
from ``--pretty false`` output — a stable, documented format. Same ``rule_id``
and ``100 - errors * 5`` scoring as the Python type rule.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from axm_audit.core.framework import Framework
from axm_audit.core.rules.base import PASS_THRESHOLD, register_rule
from axm_audit.core.rules.node._base import NodeToolRule
from axm_audit.models.results import CheckResult, Severity

__all__ = ["NodeTypeCheckRule"]

# tsc --pretty false emits one line per diagnostic: "file(l,c): error TSxxxx: …".
_ERROR_LINE = re.compile(r"\berror TS\d+\b")


def _count_type_errors(stdout: str) -> int:
    """Count ``error TSxxxx`` diagnostics in ``tsc --pretty false`` output."""
    return sum(1 for line in stdout.splitlines() if _ERROR_LINE.search(line))


@register_rule("type", framework=Framework.NODE)
class NodeTypeCheckRule(NodeToolRule):
    """Run ``tsc --noEmit`` and score by the TypeScript error count.

    Scoring: ``100 - errors * 5``, min 0 — identical to the Python type rule.
    """

    binary = "tsc"
    install_hint = "Install TypeScript: npm install -D typescript"

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule (shared with the Python type rule)."""
        return "QUALITY_TYPE"

    @property
    def args(self) -> list[str]:
        """Type-check without emitting, with a parseable (non-pretty) format."""
        return ["--noEmit", "--pretty", "false"]

    @property
    def findings_returncodes(self) -> frozenset[int]:
        """tsc exits 1 or 2 when it *found* type errors — not an env failure."""
        return frozenset({1, 2})

    def parse(self, result: subprocess.CompletedProcess[str]) -> object:
        """tsc emits text, not JSON — return raw stdout for scoring."""
        return result.stdout

    def score_output(self, parsed: object, project_path: Path) -> CheckResult:
        """Score by the count of ``error TSxxxx`` diagnostics."""
        stdout = parsed if isinstance(parsed, str) else ""
        error_count = _count_type_errors(stdout)
        score = max(0, 100 - error_count * 5)
        passed = score >= PASS_THRESHOLD
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Type score: {score}/100 ({error_count} errors)",
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=score,
            details={"error_count": error_count},
            fix_hint="Fix the tsc errors above" if error_count > 0 else None,
        )
