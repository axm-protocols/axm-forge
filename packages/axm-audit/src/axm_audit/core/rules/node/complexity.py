"""Node complexity rule — the ESLint pendant of :class:`ComplexityRule`.

Ports the intent of ``QUALITY_COMPLEXITY`` (cc < 10, cog < 15 — the SonarSource
2025 thresholds the Python rule also uses) to TypeScript. Both metrics come from
a single ``eslint --format json`` run, filtered by ``ruleId``:

* ``complexity`` (ESLint core) → cyclomatic
* ``sonarjs/cognitive-complexity`` (eslint-plugin-sonarjs) → cognitive

The project's ESLint config must enable both at the AXM thresholds; this rule
scores whatever the configured ESLint reports, so the thresholds live in the
project's ``eslint.config.js`` (the scaffolded template wires them up).
"""

from __future__ import annotations

from pathlib import Path

from axm_audit.core.framework import Framework
from axm_audit.core.rules.base import PASS_THRESHOLD, register_rule
from axm_audit.core.rules.node._base import NodeToolRule
from axm_audit.models.results import CheckResult, Severity

__all__ = ["NodeComplexityRule"]

# Per-violation penalty — matches the Python ComplexityRule (10 points each).
_PENALTY = 10
_COMPLEXITY_RULE_IDS = frozenset({"complexity", "sonarjs/cognitive-complexity"})


def _count_complexity_messages(eslint_json: list[dict[str, object]]) -> int:
    """Count ESLint messages whose ruleId is a complexity metric."""
    total = 0
    for entry in eslint_json:
        messages = entry.get("messages", [])
        if not isinstance(messages, list):
            continue
        for msg in messages:
            if isinstance(msg, dict) and msg.get("ruleId") in _COMPLEXITY_RULE_IDS:
                total += 1
    return total


@register_rule("complexity", framework=Framework.NODE)
class NodeComplexityRule(NodeToolRule):
    """Score cyclomatic + cognitive complexity findings from ESLint.

    Scoring: ``100 - violations * 10``, min 0 — identical to the Python rule.
    """

    binary = "eslint"
    install_hint = (
        "Install ESLint + sonarjs: npm install -D eslint eslint-plugin-sonarjs"
    )

    @property
    def rule_id(self) -> str:
        """Unique identifier (shared with the Python complexity rule)."""
        return "QUALITY_COMPLEXITY"

    @property
    def args(self) -> list[str]:
        """Run ESLint over the project with the JSON formatter."""
        return ["--format", "json", "."]

    def score_output(self, parsed: object, project_path: Path) -> CheckResult:
        """Score by the count of complexity-rule violations."""
        count = _count_complexity_messages(parsed) if isinstance(parsed, list) else 0
        score = max(0, 100 - count * _PENALTY)
        passed = score >= PASS_THRESHOLD
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Complexity score: {score}/100 ({count} over threshold)",
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=score,
            details={"violation_count": count},
            fix_hint=("Refactor functions above cc<10 / cog<15" if count > 0 else None),
        )
