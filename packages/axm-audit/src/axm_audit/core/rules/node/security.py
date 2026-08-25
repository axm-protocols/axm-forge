"""Node security rules — dependency vulnerabilities (npm audit) and secrets.

Ports the intent of the Python ``DEPS_AUDIT`` (vulnerable packages) and
``PRACTICE_SECURITY`` (hardcoded secrets) rules to the Node ecosystem.

Research note (false-green): ``npm audit --audit-level`` is an *exit-code gate*
— the JSON still lists every vuln — whereas ``pnpm audit --audit-level`` is a
JSON *filter*. We never pass ``--audit-level`` and score ``metadata`` directly.
``npm audit`` exits 1 when vulns exist (a finding, not an env failure).
"""

from __future__ import annotations

from pathlib import Path

from axm_audit.core.framework import Framework
from axm_audit.core.rules.base import register_rule
from axm_audit.core.rules.node._base import NodeToolRule
from axm_audit.models.results import CheckResult, Severity

__all__ = ["NodeSecretsRule", "NodeVulnerabilityRule"]


def _vuln_counts(parsed: object) -> tuple[int, int]:
    """Return (high, critical) vulnerability counts from ``npm audit --json``."""
    if not isinstance(parsed, dict):
        return (0, 0)
    metadata = parsed.get("metadata")
    if not isinstance(metadata, dict):
        return (0, 0)
    vulns = metadata.get("vulnerabilities")
    if not isinstance(vulns, dict):
        return (0, 0)
    high = vulns.get("high", 0)
    critical = vulns.get("critical", 0)
    return (
        high if isinstance(high, int) else 0,
        critical if isinstance(critical, int) else 0,
    )


@register_rule("deps", framework=Framework.NODE)
class NodeVulnerabilityRule(NodeToolRule):
    """Score npm-audit vulnerabilities (HIGH/CRITICAL).

    Mirrors the Python ``DEPS_AUDIT``: ``100 - (high+critical) * 15``. Lives in
    the ``deps`` category like its Python counterpart.
    """

    binary = "npm"
    on_path = True
    install_hint = "npm is required to run `npm audit`"

    @property
    def rule_id(self) -> str:
        """Unique identifier (shared with the Python dependency-audit rule)."""
        return "DEPS_AUDIT"

    @property
    def args(self) -> list[str]:
        """Full vulnerability report as JSON (no --audit-level: that's a gate)."""
        return ["audit", "--json"]

    @property
    def findings_returncodes(self) -> frozenset[int]:
        """npm audit exits 1 when vulnerabilities are present — a finding."""
        return frozenset({1})

    def score_output(self, parsed: object, project_path: Path) -> CheckResult:
        """Score by HIGH (15 each) + CRITICAL (15 each) vulnerability counts."""
        high, critical = _vuln_counts(parsed)
        total = high + critical
        score = max(0, 100 - total * 15)
        passed = total == 0
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Vulnerabilities: {critical} critical, {high} high",
            severity=Severity.ERROR if not passed else Severity.INFO,
            score=score,
            details={"high": high, "critical": critical},
            fix_hint="Run: npm audit fix" if total else None,
        )


@register_rule("security", framework=Framework.NODE)
class NodeSecretsRule(NodeToolRule):
    """Score hardcoded-secret findings from gitleaks.

    Mirrors the Python ``PRACTICE_SECURITY`` (secret scan): ``100 - secrets*25``.
    gitleaks is a system tool (not a node_modules binary); it writes its JSON
    report to stdout and exits non-zero when leaks are found.
    """

    binary = "gitleaks"
    on_path = True
    install_hint = "Install gitleaks: brew install gitleaks"

    @property
    def rule_id(self) -> str:
        """Unique identifier (shared with the Python secret-scan rule)."""
        return "PRACTICE_SECURITY"

    @property
    def args(self) -> list[str]:
        """Scan the directory, emitting the JSON report to stdout."""
        return ["dir", ".", "--report-format", "json", "--report-path", "/dev/stdout"]

    @property
    def findings_returncodes(self) -> frozenset[int]:
        """gitleaks exits 1 when leaks are found — a finding, not a crash."""
        return frozenset({1})

    def score_output(self, parsed: object, project_path: Path) -> CheckResult:
        """Score by the number of secret findings (gitleaks JSON is an array)."""
        secret_count = len(parsed) if isinstance(parsed, list) else 0
        score = max(0, 100 - secret_count * 25)
        passed = secret_count == 0
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Secrets: {secret_count} hardcoded secret(s) found",
            severity=Severity.ERROR if not passed else Severity.INFO,
            score=score,
            details={"secret_count": secret_count},
            fix_hint="Remove/rotate the leaked secrets above" if secret_count else None,
        )
