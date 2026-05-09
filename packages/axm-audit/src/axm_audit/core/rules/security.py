"""Security rules — Bandit + secret-pattern detection."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from axm_audit.core.rules._helpers import get_python_files
from axm_audit.core.rules.base import PASS_THRESHOLD, ProjectRule, register_rule
from axm_audit.core.runner import run_in_project
from axm_audit.models.results import CheckResult, Severity

logger = logging.getLogger(__name__)

# Bandit exit codes: 0 = clean, 1 = issues found, >= 2 = internal error.
_BANDIT_ERROR_RC = 2
_BANDIT_ISSUES_RC = 1


def run_bandit(src_path: Path, project_path: Path) -> dict[str, object]:
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
            data: dict[str, object] = json.loads(result.stdout)
            return data
    except json.JSONDecodeError:
        pass

    if result.returncode >= _BANDIT_ERROR_RC:
        stderr = result.stderr.strip() if result.stderr else "unknown error"
        msg = f"bandit failed (rc={result.returncode}): {stderr}"
        raise RuntimeError(msg)

    if result.returncode == _BANDIT_ISSUES_RC:
        stderr = (result.stderr or "").strip()[:500]
        logger.warning(
            "QUALITY_SECURITY: bandit returned rc=1 with empty stdout "
            "(stderr: %s) — treating as no issues found, but this may "
            "indicate a silent failure",
            stderr or "<empty>",
        )

    return {}


def _extract_top_issues(results: list[dict[str, object]]) -> list[dict[str, object]]:
    """Extract top 5 issues sorted by severity (HIGH first)."""
    sorted_issues = sorted(
        results,
        key=lambda x: (
            0 if x.get("issue_severity") == "HIGH" else 1,
            _as_int(x.get("line_number", 0)),
        ),
    )[:5]
    extracted: list[dict[str, object]] = []
    for issue in sorted_issues:
        filename_raw = issue.get("filename", "")
        filename = filename_raw if isinstance(filename_raw, str) else ""
        extracted.append(
            {
                "severity": issue.get("issue_severity"),
                "code": issue.get("test_id"),
                "message": issue.get("issue_text"),
                "file": Path(filename).name,
                "line": issue.get("line_number"),
            }
        )
    return extracted


def _as_int(value: object) -> int:
    """Best-effort int coercion for sort keys."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _count_severities(results: list[dict[str, object]]) -> tuple[int, int]:
    """Return (high, medium) severity counts from Bandit results."""
    high = sum(1 for r in results if r.get("issue_severity") == "HIGH")
    med = sum(1 for r in results if r.get("issue_severity") == "MEDIUM")
    return high, med


def _format_top_issue_lines(top_issues: list[dict[str, object]]) -> list[str]:
    """Format top issues as bullet lines for the text report."""
    lines: list[str] = []
    for i in top_issues:
        severity = i.get("severity")
        sev_letter = severity[0] if isinstance(severity, str) and severity else "?"
        lines.append(
            f"\u2022 {sev_letter} {i.get('code')} {i.get('file')}:{i.get('line')}"
            f" {i.get('message')}"
        )
    return lines


def _build_security_result(
    rule_id: str, results: list[dict[str, object]]
) -> CheckResult:
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
        score=int(score),
        details={
            "high_count": high,
            "medium_count": med,
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
            data = run_bandit(src_path, project_path)
        except FileNotFoundError:
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="bandit not available",
                severity=Severity.ERROR,
                score=0,
                details={"high_count": 0, "medium_count": 0},
                fix_hint="Install with: uv add --dev bandit",
            )
        except RuntimeError as exc:
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message=str(exc),
                severity=Severity.ERROR,
                score=0,
                details={"high_count": 0, "medium_count": 0},
                fix_hint="Check bandit installation: uv run bandit --version",
            )

        raw_results = data.get("results", [])
        results: list[dict[str, object]] = (
            [r for r in raw_results if isinstance(r, dict)]
            if isinstance(raw_results, list)
            else []
        )
        return _build_security_result(self.rule_id, results)


@dataclass
@register_rule("security")
class SecurityPatternRule(ProjectRule):
    """Detect hardcoded secrets via regex patterns."""

    patterns: list[str] = field(
        default_factory=lambda: [
            r"password\s*=\s*[\"'][^\"']+[\"']",
            r"secret\s*=\s*[\"'][^\"']+[\"']",
            r"api_key\s*=\s*[\"'][^\"']+[\"']",
            r"token\s*=\s*[\"'][^\"']+[\"']",
        ]
    )

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "PRACTICE_SECURITY"

    def _scan_file_for_secrets(
        self, path: Path, src_path: Path
    ) -> list[dict[str, str | int]]:
        try:
            content = path.read_text()
        except (OSError, UnicodeDecodeError):
            return []

        found: list[dict[str, str | int]] = []
        for pattern in self.patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                line_num = content[: match.start()].count("\n") + 1
                found.append(
                    {
                        "file": str(path.relative_to(src_path)),
                        "line": line_num,
                        "pattern": pattern.split(r"\s*")[0],
                    }
                )
        return found

    def _build_secret_result(self, matches: list[dict[str, str | int]]) -> CheckResult:
        count = len(matches)
        passed = count == 0
        score = max(0, 100 - count * 25)
        text_lines = [f"• {m['file']}:{m['line']} {m['pattern']}" for m in matches]

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"{count} potential secret(s) found",
            severity=Severity.ERROR if not passed else Severity.INFO,
            score=int(score),
            details={"secret_count": count, "matches": matches},
            text="\n".join(text_lines) if text_lines else None,
            fix_hint="Use environment variables or secret managers"
            if not passed
            else None,
        )

    def check(self, project_path: Path) -> CheckResult:
        """Check for hardcoded secrets in the project."""
        early = self.check_src(project_path)
        if early is not None:
            return early

        src_path = project_path / "src"
        matches: list[dict[str, str | int]] = []
        for path in get_python_files(src_path):
            matches.extend(self._scan_file_for_secrets(path, src_path))

        return self._build_secret_result(matches)
