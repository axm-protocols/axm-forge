"""Node lint rule — the ESLint pendant of :class:`LintingRule`.

Ports the *intent* of ``QUALITY_LINT`` (style + bugs + simplifications, zero
tolerance) to the Node ecosystem via ESLint's JSON formatter. Same scoring
(100 - issues * 2), same ``rule_id`` so workspace aggregation and downstream
consumers treat it identically to the Python lint result.
"""

from __future__ import annotations

import json
from pathlib import Path

from axm_audit.core.framework import Framework
from axm_audit.core.rules.base import LINT_PASS_THRESHOLD, ProjectRule, register_rule
from axm_audit.core.rules.node._runner import (
    ProcessVerdict,
    interpret_process,
    node_tool_available,
    run_node_tool,
)
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
class NodeLintRule(ProjectRule):
    """Run ESLint and score based on issue count (Node/Svelte projects).

    Scoring: ``100 - issue_count * 2``, min 0 — identical to the Python lint
    rule so the ``lint`` category is framework-agnostic at the scoring layer.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule (shared with the Python lint rule)."""
        return "QUALITY_LINT"

    def check(self, project_path: Path) -> CheckResult:
        """Run ESLint over the project and score by reported issue count."""
        if not (project_path / "package.json").is_file():
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message="No package.json — Node lint skipped",
                severity=Severity.INFO,
                score=100,
            )
        if not node_tool_available(project_path, "eslint"):
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="eslint not available (no node_modules/.bin/eslint, no npx)",
                severity=Severity.ERROR,
                fix_hint="Install ESLint: npm install -D eslint",
            )

        result = run_node_tool(
            "eslint",
            ["--format", "json", "."],
            project_path,
        )

        if interpret_process(result) is ProcessVerdict.ENV_FAILURE:
            return self._env_failure_result(result.returncode)

        try:
            report = json.loads(result.stdout) if result.stdout.strip() else []
        except json.JSONDecodeError:
            report = []

        issue_count = _count_messages(report) if isinstance(report, list) else 0
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

    def _env_failure_result(self, returncode: int) -> CheckResult:
        """Fail-loud result when ESLint did not complete (mirrors LintingRule)."""
        diagnostic = (
            f"audit environment unreliable — eslint did not complete "
            f"(exit code {returncode}: missing config/deps or timeout). "
            f"Run `npm install` and ensure an ESLint config exists."
        )
        return CheckResult(
            rule_id=self.rule_id,
            passed=False,
            message=f"Lint check BLOCKED: {diagnostic}",
            severity=Severity.ERROR,
            score=0,
            details={"issue_count": 0, "env_incomplete": True},
            fix_hint=diagnostic,
        )
