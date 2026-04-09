"""Dependency rules — vulnerability scanning and hygiene checks."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm_audit.core.rules.base import PASS_THRESHOLD, ProjectRule, register_rule
from axm_audit.core.runner import run_in_project
from axm_audit.models.results import CheckResult, Severity

logger = logging.getLogger(__name__)


def _run_pip_audit(project_path: Path) -> dict[str, Any] | list[Any]:
    """Run pip-audit and return parsed JSON output.

    Raises:
        RuntimeError: If pip-audit exits with an error and produces
            no parseable output.
    """
    result = run_in_project(
        ["pip-audit", "--format=json", "--output=-"],
        project_path,
        with_packages=["pip-audit"],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        if result.stdout.strip():
            data: dict[str, Any] | list[Any] = json.loads(result.stdout)
            return data
    except json.JSONDecodeError:
        pass

    if result.returncode != 0:
        stderr = result.stderr.strip() if result.stderr else "unknown error"
        msg = f"pip-audit failed (rc={result.returncode}): {stderr}"
        raise RuntimeError(msg)

    return {}


def _summarize_vuln(v: dict[str, Any]) -> dict[str, Any]:
    """Build a top_vulns summary entry for a single vulnerable package."""
    vuln_entries = v.get("vulns", [])
    return {
        "name": v.get("name", ""),
        "version": v.get("version", ""),
        "vuln_ids": [vi.get("id", "") for vi in vuln_entries],
        "fix_versions": sorted(
            {fv for vi in vuln_entries for fv in vi.get("fix_versions", [])}
        ),
    }


def _parse_vulns(data: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    """Extract vulnerable packages from pip-audit output."""
    if isinstance(data, list):
        return [d for d in data if d.get("vulns")]
    return [d for d in data.get("dependencies", []) if d.get("vulns")]


@dataclass
@register_rule("deps")
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
        except RuntimeError as exc:
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message=str(exc),
                severity=Severity.ERROR,
                details={"vuln_count": 0, "score": 0},
                fix_hint="Check pip-audit installation: uv run pip-audit --version",
            )

        vulns = _parse_vulns(data)
        vuln_count = len(vulns)
        score = max(0, 100 - vuln_count * 15)

        return CheckResult(
            rule_id=self.rule_id,
            passed=score >= PASS_THRESHOLD,
            message=(
                "No known vulnerabilities"
                if vuln_count == 0
                else f"{vuln_count} vulnerable package(s) found"
            ),
            severity=Severity.WARNING if score < PASS_THRESHOLD else Severity.INFO,
            details={
                "vuln_count": vuln_count,
                "score": score,
                "top_vulns": [_summarize_vuln(v) for v in vulns[:5]],
            },
            fix_hint=("Run: pip-audit --fix to remediate" if vuln_count > 0 else None),
        )


_FLAT_LAYOUT_EXCLUDES = {
    "tests",
    "test",
    "docs",
    "doc",
    ".venv",
    "venv",
    ".tox",
    ".nox",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "build",
    "dist",
    "examples",
    "experiments",
    ".eggs",
    "node_modules",
}


def _detect_first_party_packages(project_path: Path) -> list[str]:
    """Auto-detect first-party package names from project layout.

    Scans ``src/`` for top-level package directories (including namespace
    packages). Falls back to scanning the project root when no ``src/``
    directory exists.

    Returns an empty list if ``[tool.deptry] known_first_party`` is already
    configured in ``pyproject.toml`` — deptry's own config takes precedence.
    """
    pyproject = project_path / "pyproject.toml"
    if pyproject.exists():
        try:
            import tomllib

            data = tomllib.loads(pyproject.read_text())
            if data.get("tool", {}).get("deptry", {}).get("known_first_party"):
                return []
        except Exception:  # noqa: BLE001
            logger.debug("Failed to parse %s", pyproject, exc_info=True)

    src_dir = project_path / "src"
    if src_dir.is_dir():
        scan_root = src_dir
        exclude = {"__pycache__"}
    else:
        scan_root = project_path
        exclude = _FLAT_LAYOUT_EXCLUDES

    packages: list[str] = []
    for entry in sorted(scan_root.iterdir()):
        if not entry.is_dir() or (
            entry.name.startswith(".") and entry.name not in exclude
        ):
            continue
        if entry.name in exclude:
            continue
        # Accept directories that are packages (have __init__.py) or
        # namespace packages (contain subdirectories with __init__.py)
        packages.append(entry.name)

    return packages


def _run_deptry(project_path: Path) -> list[dict[str, Any]]:
    """Run deptry and return parsed JSON issues.

    Raises:
        RuntimeError: If deptry exits with a non-zero return code and
            produces no JSON output file.
    """
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    first_party = _detect_first_party_packages(project_path)
    cmd = ["deptry", ".", "--json-output", str(tmp_path)]
    for pkg in first_party:
        cmd.extend(["--known-first-party", pkg])

    try:
        result = run_in_project(
            cmd,
            project_path,
            with_packages=["deptry"],
            capture_output=True,
            text=True,
            check=False,
        )
        if tmp_path.exists() and tmp_path.stat().st_size > 0:
            return json.loads(tmp_path.read_text())  # type: ignore[no-any-return]

        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else "unknown error"
            msg = f"deptry failed (rc={result.returncode}): {stderr}"
            raise RuntimeError(msg)

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
@register_rule("deps")
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
        except FileNotFoundError:
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="deptry not available",
                severity=Severity.ERROR,
                details={"issue_count": 0, "score": 0},
                fix_hint="Install with: uv add --dev deptry",
            )
        except (RuntimeError, json.JSONDecodeError) as exc:
            is_runtime = isinstance(exc, RuntimeError)
            msg = f"deptry failed: {exc}" if is_runtime else "deptry output parse error"
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message=msg,
                severity=Severity.ERROR,
                details={"issue_count": 0, "score": 0},
                fix_hint="Check deptry installation: uv run deptry --version",
            )

        issue_count = len(issues)
        score = max(0, 100 - issue_count * 10)

        return CheckResult(
            rule_id=self.rule_id,
            passed=score >= PASS_THRESHOLD,
            message=(
                "Clean dependencies (0 issues)"
                if issue_count == 0
                else f"{issue_count} dependency issue(s) found"
            ),
            severity=Severity.WARNING if score < PASS_THRESHOLD else Severity.INFO,
            details={
                "issue_count": issue_count,
                "score": score,
                "top_issues": [_format_issue(i) for i in issues[:5]],
            },
            fix_hint=("Run: deptry . to see details" if issue_count > 0 else None),
        )
