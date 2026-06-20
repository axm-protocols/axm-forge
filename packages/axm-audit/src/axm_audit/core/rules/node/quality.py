"""Node quality rules — diff size (git, language-agnostic) and eslint-security.

* ``QUALITY_DIFF_SIZE`` is pure ``git diff`` and has no language specifics, so
  the node variant subclasses the Python rule and only re-declares its framework
  registration — one implementation, both ecosystems.
* ``QUALITY_SECURITY`` ports the Python bandit rule's intent via
  eslint-plugin-security, filtering ``security/*`` findings out of the same
  ESLint JSON run.
"""

from __future__ import annotations

from pathlib import Path

from axm_audit.core.framework import Framework
from axm_audit.core.rules.base import register_rule
from axm_audit.core.rules.node._base import NodeToolRule
from axm_audit.core.rules.quality_rules import DiffSizeRule
from axm_audit.models.results import CheckResult, Severity

__all__ = ["NodeDiffSizeRule", "NodeSecurityLintRule"]


@register_rule("lint", framework=Framework.NODE)
class NodeDiffSizeRule(DiffSizeRule):
    """Diff-size rule for node projects — identical git-based logic.

    ``git diff`` is language-agnostic, so this reuses the Python
    implementation wholesale; only the framework registration differs.
    Lives in ``lint`` like the Python ``DiffSizeRule``.
    """


def _count_security_messages(eslint_json: list[dict[str, object]]) -> int:
    """Count ESLint messages whose ruleId is an eslint-plugin-security rule."""
    total = 0
    for entry in eslint_json:
        messages = entry.get("messages", [])
        if not isinstance(messages, list):
            continue
        for msg in messages:
            rule_id = msg.get("ruleId") if isinstance(msg, dict) else None
            if isinstance(rule_id, str) and rule_id.startswith("security/"):
                total += 1
    return total


@register_rule("security", framework=Framework.NODE)
class NodeSecurityLintRule(NodeToolRule):
    """Score eslint-plugin-security findings (the bandit pendant for TS/JS).

    Mirrors the Python ``QUALITY_SECURITY``: ``100 - findings * 15``. Reuses the
    project's ESLint config (which must enable eslint-plugin-security) and
    filters the ``security/*`` ruleIds from the JSON output.
    """

    binary = "eslint"
    install_hint = (
        "Install eslint-plugin-security: npm install -D eslint-plugin-security"
    )

    @property
    def rule_id(self) -> str:
        """Unique identifier (shared with the Python security rule)."""
        return "QUALITY_SECURITY"

    @property
    def args(self) -> list[str]:
        """Run ESLint over the project with the JSON formatter."""
        return ["--format", "json", "."]

    def score_output(self, parsed: object, project_path: Path) -> CheckResult:
        """Score by the count of eslint-plugin-security findings."""
        count = _count_security_messages(parsed) if isinstance(parsed, list) else 0
        score = max(0, 100 - count * 15)
        passed = count == 0
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Security: {count} eslint-security finding(s)",
            severity=Severity.ERROR if not passed else Severity.INFO,
            score=score,
            details={"finding_count": count},
            fix_hint="Address the eslint-plugin-security findings" if count else None,
        )
