"""Knip-backed rules — dependencies hygiene and dead code.

Knip (depcheck + ts-prune are archived as of 2025, both recommend knip) reports
unused/unlisted dependencies AND unused files/exports in one tool. We run it
with ``--no-exit-code`` so the process never fails on findings — the JSON is the
source of truth, and a genuine tool crash surfaces as a non-zero exit that the
base treats as an env-failure (knip exit 2 = exception, not findings).

Knip's JSON ``--reporter json`` shape (v5):
    {"files": [...], "issues": [{"file": "...", "dependencies": [...],
     "unlisted": [...], "exports": [...], "types": [...], ...}, ...]}
``files`` is the list of unused *files*; each ``issues`` entry groups the other
issue kinds per source file.
"""

from __future__ import annotations

from pathlib import Path

from axm_audit.core.framework import Framework
from axm_audit.core.rules.base import PASS_THRESHOLD, register_rule
from axm_audit.core.rules.node._base import NodeToolRule
from axm_audit.models.results import CheckResult, Severity

__all__ = ["NodeDeadCodeRule", "NodeDependencyRule"]

_DEP_KINDS = ("dependencies", "devDependencies", "optionalPeerDependencies", "unlisted")
_DEAD_KINDS = ("exports", "types", "nsExports", "nsTypes", "enumMembers")


def _sum_issue_kinds(parsed: object, kinds: tuple[str, ...]) -> int:
    """Sum the lengths of the given issue-kind arrays across knip's ``issues``."""
    if not isinstance(parsed, dict):
        return 0
    issues = parsed.get("issues", [])
    if not isinstance(issues, list):
        return 0
    total = 0
    for entry in issues:
        if not isinstance(entry, dict):
            continue
        for kind in kinds:
            value = entry.get(kind)
            if isinstance(value, list):
                total += len(value)
            elif isinstance(value, dict):
                total += len(value)
    return total


def _count_unused_files(parsed: object) -> int:
    """Count knip's top-level unused ``files`` list."""
    if isinstance(parsed, dict):
        files = parsed.get("files", [])
        if isinstance(files, list):
            return len(files)
    return 0


class _KnipRule(NodeToolRule):
    """Shared knip invocation: JSON reporter, never fail on findings."""

    binary = "knip"
    install_hint = "Install knip: npm install -D knip"

    @property
    def args(self) -> list[str]:
        """Emit JSON and never exit non-zero on findings (we score the JSON)."""
        return ["--reporter", "json", "--no-exit-code"]


@register_rule("deps", framework=Framework.NODE)
class NodeDependencyRule(_KnipRule):
    """Score unused + unlisted dependency hygiene (knip).

    Mirrors the Python ``DependencyHygieneRule``: ``100 - issues * 10``.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "DEPS_HYGIENE"

    def score_output(self, parsed: object, project_path: Path) -> CheckResult:
        """Score by the count of unused/unlisted dependency issues."""
        count = _sum_issue_kinds(parsed, _DEP_KINDS)
        score = max(0, 100 - count * 10)
        passed = score >= PASS_THRESHOLD
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Dependency hygiene: {score}/100 ({count} issues)",
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=score,
            details={"issue_count": count},
            fix_hint="Remove unused / declare unlisted deps" if count else None,
        )


# Dead code shares the Python DeadCodeRule's category (``lint``), not a
# standalone ``dead_code`` category (which is not a valid audit category).
@register_rule("lint", framework=Framework.NODE)
class NodeDeadCodeRule(_KnipRule):
    """Score unused files + unused exports (knip).

    Mirrors the Python ``DeadCodeRule`` (category ``lint``): ``100 - items*10``.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier (shared with the Python dead-code rule)."""
        return "QUALITY_DEAD_CODE"

    def score_output(self, parsed: object, project_path: Path) -> CheckResult:
        """Score by the count of unused files + unused exports/types."""
        count = _count_unused_files(parsed) + _sum_issue_kinds(parsed, _DEAD_KINDS)
        score = max(0, 100 - count * 10)
        passed = score >= PASS_THRESHOLD
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Dead code: {score}/100 ({count} unused)",
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=score,
            details={"unused_count": count},
            fix_hint="Remove unused files / exports" if count else None,
        )
