"""Security rules — Bandit integration for vulnerability detection."""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from axm_audit.core.rules.base import ProjectRule
from axm_audit.models.results import CheckResult, Severity


@dataclass
class SecurityRule(ProjectRule):
    """Run Bandit and score based on vulnerability severity.

    Scoring: 100 - (high_count * 15 + medium_count * 5), min 0.
    High severity = 15 points penalty (critical vulnerabilities).
    Medium severity = 5 points penalty.
    Low severity = ignored (noise).
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "QUALITY_SECURITY"

    def check(self, project_path: Path) -> CheckResult:
        """Check project security with Bandit."""
        src_path = project_path / "src"
        if not src_path.exists():
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="src/ directory not found",
                severity=Severity.ERROR,
            )

        result = subprocess.run(  # noqa: S603
            ["bandit", "-r", "-f", "json", str(src_path)],  # noqa: S607
            capture_output=True,
            check=False,
            text=True,
        )

        try:
            data = json.loads(result.stdout) if result.stdout.strip() else {}
        except json.JSONDecodeError:
            data = {}

        # Count by severity
        results = data.get("results", [])
        high_count = sum(1 for r in results if r.get("issue_severity") == "HIGH")
        medium_count = sum(1 for r in results if r.get("issue_severity") == "MEDIUM")

        # Extract top 5 issues (HIGH first, then MEDIUM)
        sorted_issues = sorted(
            results,
            key=lambda x: (
                0 if x.get("issue_severity") == "HIGH" else 1,
                x.get("line_number", 0),
            ),
        )[:5]

        top_issues = [
            {
                "severity": issue.get("issue_severity"),
                "code": issue.get("test_id"),
                "message": issue.get("issue_text"),
                "file": Path(issue.get("filename", "")).name,
                "line": issue.get("line_number"),
            }
            for issue in sorted_issues
        ]

        # Scoring: HIGH = -15, MEDIUM = -5
        score = max(0, 100 - (high_count * 15 + medium_count * 5))
        passed = score >= 80

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=(
                f"Security score: {score}/100 "
                f"({high_count} high, {medium_count} medium severity issues)"
            ),
            severity=Severity.WARNING if not passed else Severity.INFO,
            details={
                "high_count": high_count,
                "medium_count": medium_count,
                "score": score,
                "top_issues": top_issues,
            },
            fix_hint=(
                "Review and fix security vulnerabilities. "
                "Run: bandit -r src/ for details"
                if high_count > 0 or medium_count > 0
                else None
            ),
        )
