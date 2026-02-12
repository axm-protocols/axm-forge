"""Dependency rules — vulnerability scanning and hygiene checks."""

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from axm_audit.core.rules.base import ProjectRule
from axm_audit.models.results import CheckResult, Severity


@dataclass
class DependencyAuditRule(ProjectRule):
    """Scan dependencies for known vulnerabilities via pip-audit.

    Scoring: 100 - (vuln_count * 15), min 0.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "DEPS_AUDIT"

    def check(self, project_path: Path) -> CheckResult:
        """Check dependencies for known CVEs."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip_audit", "--format=json", "--output=-"],
                capture_output=True,
                text=True,
                check=False,
                cwd=str(project_path),
            )
        except FileNotFoundError:
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="pip-audit not available",
                severity=Severity.ERROR,
                details={"vuln_count": 0, "score": 0},
                fix_hint="Install with: uv add --dev pip-audit",
            )

        try:
            data = json.loads(result.stdout) if result.stdout.strip() else {}
        except json.JSONDecodeError:
            data = {}

        # pip-audit JSON: {"dependencies": [...]} or bare list
        if isinstance(data, list):
            vulns = [d for d in data if d.get("vulns")]
        else:
            vulns = [d for d in data.get("dependencies", []) if d.get("vulns")]

        vuln_count = len(vulns)
        score = max(0, 100 - vuln_count * 15)
        passed = score >= 80

        top_vulns = [
            {
                "name": v.get("name", ""),
                "version": v.get("version", ""),
            }
            for v in vulns[:5]
        ]

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=(
                "No known vulnerabilities"
                if vuln_count == 0
                else f"{vuln_count} vulnerable package(s) found"
            ),
            severity=Severity.WARNING if not passed else Severity.INFO,
            details={
                "vuln_count": vuln_count,
                "score": score,
                "top_vulns": top_vulns,
            },
            fix_hint=("Run: pip-audit --fix to remediate" if vuln_count > 0 else None),
        )


@dataclass
class DependencyHygieneRule(ProjectRule):
    """Check for unused/missing/transitive dependencies via deptry.

    Scoring: 100 - (issue_count * 10), min 0.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "DEPS_HYGIENE"

    def check(self, project_path: Path) -> CheckResult:
        """Check dependency hygiene with deptry."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "deptry", ".", "--json-output", "-"],
                capture_output=True,
                text=True,
                check=False,
                cwd=str(project_path),
            )
        except FileNotFoundError:
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="deptry not available",
                severity=Severity.ERROR,
                details={"issue_count": 0, "score": 0},
                fix_hint="Install with: uv add --dev deptry",
            )

        try:
            issues = json.loads(result.stdout) if result.stdout.strip() else []
        except json.JSONDecodeError:
            issues = []

        issue_count = len(issues)
        score = max(0, 100 - issue_count * 10)
        passed = score >= 80

        top_issues = [
            {
                "code": i.get("error_code", ""),
                "module": i.get("module", ""),
                "message": i.get("message", ""),
            }
            for i in issues[:5]
        ]

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=(
                "Clean dependencies (0 issues)"
                if issue_count == 0
                else f"{issue_count} dependency issue(s) found"
            ),
            severity=Severity.WARNING if not passed else Severity.INFO,
            details={
                "issue_count": issue_count,
                "score": score,
                "top_issues": top_issues,
            },
            fix_hint=("Run: deptry . to see details" if issue_count > 0 else None),
        )
