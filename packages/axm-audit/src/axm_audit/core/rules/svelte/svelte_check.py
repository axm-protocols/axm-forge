"""Svelte type + a11y rule — ``svelte-check`` (the delta ``tsc`` cannot cover).

``tsc`` cannot type-check inside ``.svelte`` files, and Svelte's a11y warnings
come from the compiler, not an ESLint plugin. ``svelte-check`` covers both. This
rule contributes to the ``type`` category (alongside the node ``tsc`` rule) and
is registered under ``framework=svelte`` so only Svelte projects run it.

``svelte-check --output machine`` emits space-separated rows, one per
diagnostic, each starting with a timestamp then ERROR/WARNING. We count ERROR
rows. False-green guard (research): svelte-check must point at the app tsconfig
that resolves ``$lib`` (run ``svelte-kit sync`` first) or it analyses nothing.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from axm_audit.core.framework import Framework
from axm_audit.core.rules.base import PASS_THRESHOLD, register_rule
from axm_audit.core.rules.node._base import NodeToolRule
from axm_audit.models.results import CheckResult, Severity

__all__ = ["SvelteCheckRule"]


# A machine row is "<ts> <LEVEL> ...": the level is the 2nd whitespace field.
_MIN_ROW_FIELDS = 2


def _count_errors(output: str) -> int:
    """Count ERROR diagnostics in ``svelte-check --output machine`` rows."""
    count = 0
    for line in output.splitlines():
        # Machine rows look like: "<ts> ERROR \"file\" <line>:<col> \"msg\"".
        parts = line.split(maxsplit=2)
        if len(parts) >= _MIN_ROW_FIELDS and parts[1] == "ERROR":
            count += 1
    return count


@register_rule("type", framework=Framework.SVELTE)
class SvelteCheckRule(NodeToolRule):
    """Run ``svelte-check`` and score by its error count.

    Scoring: ``100 - errors * 5`` (same per-error weight as the type rule).
    Contributes to the ``type`` category for Svelte projects on top of ``tsc``.
    """

    binary = "svelte-check"
    install_hint = "Install svelte-check: npm install -D svelte-check"

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "SVELTE_CHECK"

    @property
    def args(self) -> list[str]:
        """Machine-readable output, errors-only threshold."""
        return ["--output", "machine", "--threshold", "error"]

    @property
    def findings_returncodes(self) -> frozenset[int]:
        """svelte-check exits 1 when it found errors — a finding, not a crash."""
        return frozenset({1})

    def parse(self, result: subprocess.CompletedProcess[str]) -> object:
        """svelte-check emits text rows, not JSON — return raw stdout."""
        return result.stdout

    def score_output(self, parsed: object, project_path: Path) -> CheckResult:
        """Score by the count of svelte-check ERROR diagnostics."""
        output = parsed if isinstance(parsed, str) else ""
        error_count = _count_errors(output)
        score = max(0, 100 - error_count * 5)
        passed = score >= PASS_THRESHOLD
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"svelte-check: {score}/100 ({error_count} errors)",
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=score,
            details={"error_count": error_count},
            fix_hint="Fix the svelte-check errors above" if error_count else None,
        )
