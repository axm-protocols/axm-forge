"""Node architecture rules — circular imports (madge) and duplication (jscpd).

Ports the intent of the Python ``ARCH_CIRCULAR`` and ``ARCH_DUPLICATION`` rules
to the Node ecosystem. Both register under the ``architecture`` category (where
the Python ``CircularImportRule`` and ``DuplicationRule`` live).

False-green guard (from the research): madge/dependency-cruiser must resolve TS
path aliases (``$lib``, ``@/``) or they silently analyse nothing. The scaffolded
template emits a ``.madgerc`` pointing at ``tsconfig.json`` so aliases resolve.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from axm_audit.core.framework import Framework
from axm_audit.core.rules.base import PASS_THRESHOLD, register_rule
from axm_audit.core.rules.node._base import NodeToolRule
from axm_audit.core.rules.node._runner import (
    ProcessVerdict,
    interpret_process,
    node_tool_available,
    run_node_tool,
)
from axm_audit.models.results import CheckResult, Severity

__all__ = ["NodeCircularImportRule", "NodeDuplicationRule"]


@register_rule("architecture", framework=Framework.NODE)
class NodeCircularImportRule(NodeToolRule):
    """Score circular-import cycles found by ``madge --circular --json``.

    Mirrors the Python ``CircularImportRule``: ``100 - cycles * 20``.
    ``madge --circular --json`` returns a JSON array of cycles (each a list of
    files); an empty array means no cycles.
    """

    binary = "madge"
    install_hint = "Install madge: npm install -D madge"

    @property
    def rule_id(self) -> str:
        """Unique identifier (shared with the Python circular-import rule)."""
        return "ARCH_CIRCULAR"

    @property
    def args(self) -> list[str]:
        """Report circular dependencies as JSON over the source tree."""
        return ["--circular", "--json", "src"]

    def score_output(self, parsed: object, project_path: Path) -> CheckResult:
        """Score by the number of import cycles."""
        cycle_count = len(parsed) if isinstance(parsed, list) else 0
        score = max(0, 100 - cycle_count * 20)
        passed = score >= PASS_THRESHOLD
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Circular imports: {cycle_count} cycle(s)",
            severity=Severity.ERROR if not passed else Severity.INFO,
            score=score,
            details={"cycle_count": cycle_count},
            fix_hint="Break the import cycles above" if cycle_count else None,
        )


def _jscpd_percentage(parsed: object) -> float:
    """Extract the duplicated-token percentage from jscpd's JSON report."""
    if not isinstance(parsed, dict):
        return 0.0
    statistics = parsed.get("statistics")
    if not isinstance(statistics, dict):
        return 0.0
    total = statistics.get("total")
    if not isinstance(total, dict):
        return 0.0
    pct = total.get("percentage", 0)
    return float(pct) if isinstance(pct, int | float) else 0.0


@register_rule("architecture", framework=Framework.NODE)
class NodeDuplicationRule(NodeToolRule):
    """Score code duplication found by ``jscpd --reporters json``.

    Mirrors the Python ``DuplicationRule`` intent. jscpd reports a duplicated
    percentage; we map it to a score (0% → 100, ≥10% → 0) and pass below a 3%
    duplication threshold (the research's recommended ceiling).
    """

    binary = "jscpd"
    install_hint = "Install jscpd: npm install -D jscpd"
    _MAX_TOLERATED_PCT = 10.0
    _PASS_PCT = 3.0

    @property
    def rule_id(self) -> str:
        """Unique identifier (shared with the Python duplication rule)."""
        return "ARCH_DUPLICATION"

    @property
    def args(self) -> list[str]:
        """Placeholder — :meth:`check` builds the argv with a real output dir."""
        return ["--reporters", "json", "--silent", "src"]

    def check(self, project_path: Path) -> CheckResult:
        """Run jscpd, reading the percentage from its JSON *report file*.

        jscpd's ``json`` reporter writes ``jscpd-report.json`` to an output
        directory; **nothing structured lands on stdout** (only a one-line human
        summary). The base :class:`NodeToolRule.parse` JSON-decodes stdout, which
        for jscpd always yields ``[]`` → pct 0 → a permanent false-green. So this
        rule reads the report file instead of stdout.
        """
        if not (project_path / "package.json").is_file():
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message="No package.json — jscpd skipped",
                severity=Severity.INFO,
                score=100,
            )
        if not node_tool_available(project_path, self.binary):
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message=f"{self.binary} not available "
                f"(not on node_modules/.bin/{self.binary})",
                severity=Severity.ERROR,
                fix_hint=self.install_hint,
            )
        with tempfile.TemporaryDirectory() as report_dir:
            result = run_node_tool(
                self.binary,
                ["--reporters", "json", "--output", report_dir, "--silent", "src"],
                project_path,
                on_path=False,
            )
            if interpret_process(result) is ProcessVerdict.ENV_FAILURE:
                return self.env_failure_result(result.returncode)
            report = Path(report_dir) / "jscpd-report.json"
            try:
                parsed = json.loads(report.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                parsed = {}
        return self.score_output(parsed, project_path)

    def score_output(self, parsed: object, project_path: Path) -> CheckResult:
        """Score inversely to the duplicated-token percentage."""
        pct = _jscpd_percentage(parsed)
        score = max(0, round(100 - (pct / self._MAX_TOLERATED_PCT) * 100))
        passed = pct <= self._PASS_PCT
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Duplication: {pct:.1f}% ({score}/100)",
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=score,
            details={"duplication_pct": pct},
            fix_hint="Reduce duplicated code blocks" if not passed else None,
        )
