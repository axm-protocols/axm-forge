"""Security rules — Bandit integration for vulnerability detection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm_audit.core.rules.base import PASS_THRESHOLD, ProjectRule, register_rule
from axm_audit.core.runner import run_in_project
from axm_audit.models.results import CheckResult, Severity

# Bandit exit codes: 0 = clean, 1 = issues found, >= 2 = internal error.
_BANDIT_ERROR_RC = 2


def _run_bandit(src_path: Path, project_path: Path) -> dict[str, Any]:
    """Run Bandit and return parsed JSON output.

    Raises:
        RuntimeError: If bandit exits with rc >= 2 (error) and produces
            no parseable output.  rc=0 means clean, rc=1 means issues found.
    """
    result = run_in_project(
        ["bandit", "-r", "-f", "json", str(src_path)],
        project_path,
        with_packages=["bandit"],
        capture_output=True,
        check=False,
        text=True,
    )
    try:
        if result.stdout.strip():
            data: dict[str, Any] = json.loads(result.stdout)
            return data
    except json.JSONDecodeError:
        pass

    # rc=0 or rc=1 with empty stdout is fine (no issues / banner only)
    if result.returncode >= _BANDIT_ERROR_RC:
        stderr = result.stderr.strip() if result.stderr else "unknown error"
        msg = f"bandit failed (rc={result.returncode}): {stderr}"
        raise RuntimeError(msg)

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


def _count_severities(results: list[dict[str, Any]]) -> tuple[int, int]:
    """Return (high, medium) severity counts from Bandit results."""
    high = sum(1 for r in results if r.get("issue_severity") == "HIGH")
    med = sum(1 for r in results if r.get("issue_severity") == "MEDIUM")
    return high, med


def _format_top_issue_lines(top_issues: list[dict[str, Any]]) -> list[str]:
    """Format top issues as bullet lines for the text report."""
    return [
        f"\u2022 {i['severity'][0]} {i['code']} {i['file']}:{i['line']} {i['message']}"
        for i in top_issues
    ]


def _build_security_result(rule_id: str, results: list[dict[str, Any]]) -> CheckResult:
    """Assemble a CheckResult from Bandit scan results.

    Aggregates severity counts, derives a 0-100 score (HIGH=-15, MEDIUM=-5),
    extracts the top issues, and formats them as text lines.
    """
    high, med = _count_severities(results)
    score = max(0, 100 - (high * 15 + med * 5))
    top_issues = _extract_top_issues(results)
    text_lines = _format_top_issue_lines(top_issues)

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
            "top_issues": top_issues,
        },
        text="\n".join(text_lines) if text_lines else None,
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
        except RuntimeError as exc:
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message=str(exc),
                severity=Severity.ERROR,
                details={"high_count": 0, "medium_count": 0, "score": 0},
                fix_hint="Check bandit installation: uv run bandit --version",
            )

        return _build_security_result(self.rule_id, data.get("results", []))
