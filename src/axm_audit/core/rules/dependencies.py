"""Dependency rules — vulnerability scanning and hygiene checks."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm_audit.core.rules.base import ProjectRule
from axm_audit.core.runner import run_in_project
from axm_audit.models.results import CheckResult, Severity


def _run_pip_audit(project_path: Path) -> dict[str, Any] | list[Any]:
    """Run pip-audit and return parsed JSON output."""
    result = run_in_project(
        ["pip-audit", "--format=json", "--output=-"],
        project_path,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        return json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        return {}


def _parse_vulns(data: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    """Extract vulnerable packages from pip-audit output."""
    if isinstance(data, list):
        return [d for d in data if d.get("vulns")]
    return [d for d in data.get("dependencies", []) if d.get("vulns")]


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
            data = _run_pip_audit(project_path)
        except FileNotFoundError:
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="pip-audit not available",
                severity=Severity.ERROR,
                details={"vuln_count": 0, "score": 0},
                fix_hint="Install with: uv add --dev pip-audit",
            )

        vulns = _parse_vulns(data)
        vuln_count = len(vulns)
        score = max(0, 100 - vuln_count * 15)

        return CheckResult(
            rule_id=self.rule_id,
            passed=score >= 80,
            message=(
                "No known vulnerabilities"
                if vuln_count == 0
                else f"{vuln_count} vulnerable package(s) found"
            ),
            severity=Severity.WARNING if score < 80 else Severity.INFO,
            details={
                "vuln_count": vuln_count,
                "score": score,
                "top_vulns": [
                    {"name": v.get("name", ""), "version": v.get("version", "")}
                    for v in vulns[:5]
                ],
            },
            fix_hint=("Run: pip-audit --fix to remediate" if vuln_count > 0 else None),
        )


def _run_deptry(project_path: Path) -> list[dict[str, Any]]:
    """Run deptry and return parsed JSON issues."""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        run_in_project(
            ["deptry", ".", "--json-output", str(tmp_path)],
            project_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if tmp_path.exists() and tmp_path.stat().st_size > 0:
            return json.loads(tmp_path.read_text())  # type: ignore[no-any-return]
        return []
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _format_issue(issue: dict[str, Any]) -> dict[str, str]:
    """Format a single deptry issue for reporting."""
    if "error" in issue:
        code = issue["error"].get("code", "")
        message = issue["error"].get("message", "")
    else:
        code = issue.get("error_code", "")
        message = issue.get("message", "")
    return {"code": code, "module": issue.get("module", ""), "message": message}


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
            issues = _run_deptry(project_path)
        except (FileNotFoundError, json.JSONDecodeError):
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="deptry failed or missing",
                severity=Severity.ERROR,
                details={"issue_count": 0, "score": 0},
                fix_hint="Install with: uv add --dev deptry",
            )

        issue_count = len(issues)
        score = max(0, 100 - issue_count * 10)

        return CheckResult(
            rule_id=self.rule_id,
            passed=score >= 80,
            message=(
                "Clean dependencies (0 issues)"
                if issue_count == 0
                else f"{issue_count} dependency issue(s) found"
            ),
            severity=Severity.WARNING if score < 80 else Severity.INFO,
            details={
                "issue_count": issue_count,
                "score": score,
                "top_issues": [_format_issue(i) for i in issues[:5]],
            },
            fix_hint=("Run: deptry . to see details" if issue_count > 0 else None),
        )
