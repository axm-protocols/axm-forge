"""Node lint rule — the ESLint pendant of :class:`LintingRule`.

Ports the *intent* of ``QUALITY_LINT`` (style + bugs + simplifications, zero
tolerance) to the Node ecosystem via ESLint's JSON formatter. Same scoring
(100 - issues * 2), same ``rule_id`` so workspace aggregation and downstream
consumers treat it identically to the Python lint result.
"""

from __future__ import annotations

from pathlib import Path

from axm_audit.core.framework import Framework
from axm_audit.core.rules.base import LINT_PASS_THRESHOLD, register_rule
from axm_audit.core.rules.node._base import NodeToolRule
from axm_audit.models.results import CheckResult, Severity

__all__ = ["NodeLintRule"]


def _count_messages(eslint_json: list[dict[str, object]]) -> int:
    """Sum ESLint ``errorCount`` + ``warningCount`` across all files."""
    total = 0
    for entry in eslint_json:
        for key in ("errorCount", "warningCount"):
            value = entry.get(key, 0)
            if isinstance(value, int):
                total += value
    return total


@register_rule("lint", framework=Framework.NODE)
class NodeLintRule(NodeToolRule):
    """Run ESLint and score based on issue count (Node/Svelte/React projects).

    Scoring: ``100 - issue_count * 2``, min 0 — identical to the Python lint
    rule so the ``lint`` category is framework-agnostic at the scoring layer.
    """

    binary = "eslint"
    install_hint = "Install ESLint: npm install -D eslint"

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule (shared with the Python lint rule)."""
        return "QUALITY_LINT"

    @property
    def args(self) -> list[str]:
        """Run ESLint over the whole project with the JSON formatter."""
        return ["--format", "json", "."]

    def score_output(self, parsed: object, project_path: Path) -> CheckResult:
        """Score by the total ESLint error + warning count."""
        issue_count = _count_messages(parsed) if isinstance(parsed, list) else 0
        score = max(0, 100 - issue_count * 2)
        passed = score >= LINT_PASS_THRESHOLD
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Lint score: {score}/100 ({issue_count} issues)",
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=int(score),
            details={"issue_count": issue_count},
            fix_hint="Run: npx eslint --fix ." if issue_count > 0 else None,
        )
