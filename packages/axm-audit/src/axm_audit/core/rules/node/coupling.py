"""Node god-class and coupling rules — backed by axm-ast structural metrics.

Unlike the other node rules (which shell out to ESLint/knip/madge), these read
*structural facts* that axm-ast already computes from the TS AST and dependency
graph: class size/method-count and per-module fan-out. axm-ast is the source of
truth for the fact; this rule only applies the AXM threshold — the same split as
the Python ``GodClassRule`` / ``CouplingMetricRule`` (which compute on the Python
AST). One axm-ast implementation thus powers both languages.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from axm_audit.core.framework import Framework
from axm_audit.core.rules.base import ProjectRule, register_rule
from axm_audit.models.results import CheckResult, Severity

if TYPE_CHECKING:
    from pathlib import Path

    from axm_ast.models.nodes import PackageInfo

__all__ = ["NodeCouplingRule", "NodeGodClassRule"]

_GOD_CLASS_PENALTY = 15
_COUPLING_PENALTY = 5
_FAN_OUT_THRESHOLD = 10


def _analyze(project_path: Path) -> PackageInfo | None:
    """Analyze the node package via axm-ast, or None if it cannot be analysed.

    Imported lazily so axm-audit does not pay the axm-ast import at module load.
    """
    try:
        from axm_ast.core.analyzer import analyze_package
    except ImportError:
        return None
    try:
        return analyze_package(project_path)
    except (ValueError, OSError):
        return None


@register_rule("architecture", framework=Framework.NODE)
class NodeGodClassRule(ProjectRule):
    """Flag god classes (too many lines or methods) via axm-ast.

    Mirrors the Python ``GodClassRule``: lines > 500 or methods > 15,
    ``100 - count * 15``.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier (shared with the Python god-class rule)."""
        return "ARCH_GOD_CLASS"

    def check(self, project_path: Path) -> CheckResult:
        """Score by the count of god classes found in the package's TS classes."""
        if not (project_path / "package.json").is_file():
            return _skip(self.rule_id)
        pkg = _analyze(project_path)
        if pkg is None:
            return _unavailable(self.rule_id, "axm-ast")
        from axm_ast.core.metrics import find_god_classes

        god = find_god_classes(pkg)
        score = max(0, 100 - len(god) * _GOD_CLASS_PENALTY)
        passed = not god
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"{len(god)} god class(es) found",
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=score,
            details={
                "god_classes": [
                    f"{g.file}:{g.name} {g.lines}L/{g.methods}M" for g in god[:20]
                ]
            },
            fix_hint="Split large classes into smaller, focused ones" if god else None,
        )


@register_rule("architecture", framework=Framework.NODE)
class NodeCouplingRule(ProjectRule):
    """Flag over-coupled modules (high fan-out) via axm-ast.

    Mirrors the Python ``CouplingMetricRule``: modules with fan-out > 10,
    ``100 - count * 5``.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier (shared with the Python coupling rule)."""
        return "ARCH_COUPLING"

    def check(self, project_path: Path) -> CheckResult:
        """Score by the count of modules whose fan-out exceeds the threshold."""
        if not (project_path / "package.json").is_file():
            return _skip(self.rule_id)
        pkg = _analyze(project_path)
        if pkg is None:
            return _unavailable(self.rule_id, "axm-ast")
        from axm_ast.core.metrics import compute_coupling

        metrics = compute_coupling(pkg)
        over = metrics.over_fan_out(_FAN_OUT_THRESHOLD)
        score = max(0, 100 - len(over) * _COUPLING_PENALTY)
        passed = not over
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=(
                f"{len(over)} over-coupled module(s) "
                f"(max fan-out {metrics.max_fan_out})"
            ),
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=score,
            details={
                "max_fan_out": metrics.max_fan_out,
                "over_threshold": [f"{m.module} fo:{m.fan_out}" for m in over[:20]],
            },
            fix_hint="Reduce imports in the listed modules" if over else None,
        )


def _skip(rule_id: str) -> CheckResult:
    """Skip result for a non-node directory."""
    return CheckResult(
        rule_id=rule_id,
        passed=True,
        message="No package.json — skipped",
        severity=Severity.INFO,
        score=100,
    )


def _unavailable(rule_id: str, dep: str) -> CheckResult:
    """Fail-loud result when the structural analysis backend is unavailable."""
    return CheckResult(
        rule_id=rule_id,
        passed=False,
        message=f"{dep} not available — cannot compute structural metric",
        severity=Severity.ERROR,
        fix_hint=f"Install {dep} (with its TypeScript extra) to enable this rule.",
    )
