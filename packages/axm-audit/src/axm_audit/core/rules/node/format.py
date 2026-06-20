"""Node format rule — the Prettier pendant of :class:`FormattingRule`.

Ports the intent of ``QUALITY_FORMAT`` (consistent formatting) to Prettier via
``prettier --check``. Prettier exits 1 and lists each unformatted file when the
project is not fully formatted. Same ``rule_id`` and ``100 - files * 5`` scoring
as the Python format rule.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from axm_audit.core.framework import Framework
from axm_audit.core.rules.base import PASS_THRESHOLD, register_rule
from axm_audit.core.rules.node._base import NodeToolRule
from axm_audit.models.results import CheckResult, Severity

__all__ = ["NodeFormatRule"]

# Lines Prettier prints for files needing formatting start with "[warn] ".
_WARN_PREFIX = "[warn]"
# Summary/advice lines to exclude from the per-file count.
_SUMMARY_HINTS = ("Code style issues", "Forgot to run", "ran in")


def _count_unformatted(output: str) -> int:
    """Count files Prettier flagged as needing formatting.

    ``prettier --check`` prints one ``[warn] <path>`` line per unformatted file
    plus a trailing ``[warn] Code style issues found …`` summary line, which we
    exclude.
    """
    count = 0
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith(_WARN_PREFIX) and not any(
            hint in stripped for hint in _SUMMARY_HINTS
        ):
            count += 1
    return count


@register_rule("lint", framework=Framework.NODE)
class NodeFormatRule(NodeToolRule):
    """Run ``prettier --check`` and score by the unformatted-file count.

    Lives in the ``lint`` category to mirror the Python ``FormattingRule``.
    Scoring: ``100 - files * 5``, min 0.
    """

    binary = "prettier"
    install_hint = "Install Prettier: npm install -D prettier"

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule (shared with the Python format rule)."""
        return "QUALITY_FORMAT"

    @property
    def args(self) -> list[str]:
        """Check formatting across the project without writing changes."""
        return ["--check", "."]

    @property
    def findings_returncodes(self) -> frozenset[int]:
        """Prettier exits 1 when files are unformatted — that is a finding."""
        return frozenset({1})

    def parse(self, result: subprocess.CompletedProcess[str]) -> object:
        """Prettier reports unformatted files on stderr — combine both streams."""
        return f"{result.stdout}\n{result.stderr}"

    def score_output(self, parsed: object, project_path: Path) -> CheckResult:
        """Score by the count of unformatted files (parsed is combined output)."""
        output = parsed if isinstance(parsed, str) else ""
        file_count = _count_unformatted(output)
        score = max(0, 100 - file_count * 5)
        passed = score >= PASS_THRESHOLD
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Format score: {score}/100 ({file_count} unformatted)",
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=score,
            details={"unformatted_count": file_count},
            fix_hint="Run: npx prettier --write ." if file_count > 0 else None,
        )
