"""Security rules — Bandit integration for vulnerability detection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm_audit.core.rules.base import PASS_THRESHOLD, ProjectRule, register_rule
from axm_audit.core.runner import run_in_project
from axm_audit.models.results import CheckResult, Severity


def _run_bandit(src_path: Path, project_path: Path) -> dict[str, Any]:
    """Run Bandit and return parsed JSON output."""
    result = run_in_project(
        ["bandit", "-r", "-f", "json", str(src_path)],
        project_path,
        capture_output=True,
        check=False,
        text=True,
    )
    try:
        return json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        return {}


def _extract_top_issues(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract top 5 issues sorted by severity (HIGH first)."""
    sorted_issues = sorted(
        results,
        key=lambda x: (
            0 if x.get("issue_severity") == "HIGH" else 1,
            x.get("line_number", 0),
        ),
    )[:5]
    return [
        {
            "severity": issue.get("issue_severity"),
            "code": issue.get("test_id"),
            "message": issue.get("issue_text"),
            "file": Path(issue.get("filename", "")).name,
            "line": issue.get("line_number"),
        }
        for issue in sorted_issues
    ]


def _build_security_result(rule_id: str, results: list[dict[str, Any]]) -> CheckResult:
    """Build a CheckResult from Bandit scan results."""
    high = sum(1 for r in results if r.get("issue_severity") == "HIGH")
    med = sum(1 for r in results if r.get("issue_severity") == "MEDIUM")
    score = max(0, 100 - (high * 15 + med * 5))

    return CheckResult(
        rule_id=rule_id,
        passed=score >= PASS_THRESHOLD,
        message=(
            f"Security score: {score}/100 ({high} high, {med} medium severity issues)"
        ),
        severity=Severity.WARNING if score < PASS_THRESHOLD else Severity.INFO,
        details={
            "high_count": high,
            "medium_count": med,
            "score": score,
            "top_issues": _extract_top_issues(results),
        },
        fix_hint=(
            "Review and fix security vulnerabilities. Run: bandit -r src/ for details"
            if high > 0 or med > 0
            else None
        ),
    )


@dataclass
@register_rule("security")
class SecurityRule(ProjectRule):
    """Run Bandit and score based on vulnerability severity.

    Scoring: 100 - (high_count * 15 + medium_count * 5), min 0.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "QUALITY_SECURITY"

    def check(self, project_path: Path) -> CheckResult:
        """Check project security with Bandit."""
        early = self.check_src(project_path)
        if early is not None:
            return early

        src_path = project_path / "src"

        try:
            data = _run_bandit(src_path, project_path)
        except FileNotFoundError:
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="bandit not available",
                severity=Severity.ERROR,
                details={"high_count": 0, "medium_count": 0, "score": 0},
                fix_hint="Install with: uv add --dev bandit",
            )

        return _build_security_result(self.rule_id, data.get("results", []))
