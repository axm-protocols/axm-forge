"""Dependency rules — vulnerability scanning and hygiene checks."""

from __future__ import annotations

import json
import logging
import re
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


def _has_deptry_config(project_path: Path) -> bool:
    """Check if ``[tool.deptry] known_first_party`` is configured."""
    pyproject = project_path / "pyproject.toml"
    if not pyproject.exists():
        return False
    try:
        import tomllib

        data = tomllib.loads(pyproject.read_text())
    except Exception:  # noqa: BLE001
        logger.debug("Failed to parse %s", pyproject, exc_info=True)
        return False
    return bool(data.get("tool", {}).get("deptry", {}).get("known_first_party"))


def _detect_first_party_packages(project_path: Path) -> list[str]:
    """Auto-detect first-party package names from project layout.

    Scans ``src/`` for top-level package directories (including namespace
    packages). Falls back to scanning the project root when no ``src/``
    directory exists.

    Returns an empty list if ``[tool.deptry] known_first_party`` is already
    configured in ``pyproject.toml`` — deptry's own config takes precedence.
    """
    if _has_deptry_config(project_path):
        return []

    src_dir = project_path / "src"
    if src_dir.is_dir():
        scan_root = src_dir
        exclude = {"__pycache__"}
    else:
        scan_root = project_path
        exclude = _FLAT_LAYOUT_EXCLUDES

    return [
        entry.name
        for entry in sorted(scan_root.iterdir())
        if entry.is_dir()
        and not entry.name.startswith(".")
        and entry.name not in exclude
    ]


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


def _normalize_pkg(name: str) -> str:
    """Normalize a package name to underscore form for comparison."""
    return name.lower().replace("-", "_").replace(".", "_")


def _entry_point_packages(project_path: Path) -> set[str]:
    """Extract package names consumed via ``[project.entry-points]``."""
    pyproject = project_path / "pyproject.toml"
    if not pyproject.exists():
        return set()
    try:
        import tomllib

        data = tomllib.loads(pyproject.read_text())
    except Exception:  # noqa: BLE001
        return set()

    entry_points = data.get("project", {}).get("entry-points", {})
    packages: set[str] = set()
    for group in entry_points.values():
        if not isinstance(group, dict):
            continue
        for value in group.values():
            # value like "axm_init.tool:InitTool" — root module is the package
            module_path = value.split(":")[0]
            root = module_path.split(".")[0]
            packages.add(_normalize_pkg(root))
    return packages


def _optional_dep_packages(project_path: Path) -> set[str]:
    """Extract package names from ``[project.optional-dependencies]``."""
    pyproject = project_path / "pyproject.toml"
    if not pyproject.exists():
        return set()
    try:
        import tomllib

        data = tomllib.loads(pyproject.read_text())
    except Exception:  # noqa: BLE001
        return set()

    optional_deps = data.get("project", {}).get("optional-dependencies", {})
    packages: set[str] = set()
    for reqs in optional_deps.values():
        for req in reqs:
            # Strip version specifiers: take everything before [, >, <, =, ;, ~, !
            name = re.split(r"[>=<!\[;~]", req, maxsplit=1)[0].strip()
            if name:
                packages.add(_normalize_pkg(name))
    return packages


def _filter_false_positives(
    issues: list[dict[str, Any]], project_path: Path
) -> list[dict[str, Any]]:
    """Remove DEP002 false positives for entry-point and optional-dep packages."""
    allowed = _entry_point_packages(project_path) | _optional_dep_packages(project_path)
    if not allowed:
        return issues

    filtered: list[dict[str, Any]] = []
    for issue in issues:
        code = issue.get("error", {}).get("code", "") or issue.get("error_code", "")
        module = _normalize_pkg(issue.get("module", ""))
        if code == "DEP002" and module in allowed:
            continue
        filtered.append(issue)
    return filtered


def _format_issue(issue: dict[str, Any], member: str = "") -> dict[str, str]:
    """Format a single deptry issue for reporting."""
    if "error" in issue:
        code = issue["error"].get("code", "")
        message = issue["error"].get("message", "")
    else:
        code = issue.get("error_code", "")
        message = issue.get("message", "")
    formatted: dict[str, str] = {
        "code": code,
        "module": issue.get("module", ""),
        "message": message,
    }
    if member:
        formatted["member"] = member
    return formatted


def _resolve_workspace_members(project_path: Path) -> list[Path] | None:
    """Resolve workspace member paths from ``[tool.uv.workspace].members``.

    Returns ``None`` when the project is not a uv workspace.
    Directories without a ``pyproject.toml`` are silently skipped.
    """
    pyproject = project_path / "pyproject.toml"
    if not pyproject.exists():
        return None
    try:
        import tomllib

        data = tomllib.loads(pyproject.read_text())
    except Exception:  # noqa: BLE001
        return None

    workspace = data.get("tool", {}).get("uv", {}).get("workspace")
    if workspace is None:
        return None

    members: list[Path] = []
    for pattern in workspace.get("members", []):
        for match in sorted(project_path.glob(pattern)):
            if match.is_dir() and (match / "pyproject.toml").exists():
                members.append(match)
    return members


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
        members = _resolve_workspace_members(project_path)
        if members is not None:
            return self._check_workspace(project_path, members)
        result = self._check_single(project_path)
        assert isinstance(result, CheckResult)
        return result

    def _check_single(
        self, project_path: Path, *, member_name: str = ""
    ) -> CheckResult | list[dict[str, Any]]:
        """Run deptry on a single package and return a CheckResult or issue list.

        When *member_name* is set the method returns filtered issues (for
        workspace aggregation).  Otherwise it returns a full ``CheckResult``.
        """
        try:
            issues = _run_deptry(project_path)
        except FileNotFoundError:
            if member_name:
                return []
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="deptry not available",
                severity=Severity.ERROR,
                details={"issue_count": 0, "score": 0},
                fix_hint="Install with: uv add --dev deptry",
            )
        except (RuntimeError, json.JSONDecodeError) as exc:
            if member_name:
                logger.warning("deptry failed for %s: %s", member_name, exc)
                return []
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

        issues = _filter_false_positives(issues, project_path)

        if member_name:
            return issues

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

    def _check_workspace(self, project_path: Path, members: list[Path]) -> CheckResult:
        """Aggregate deptry results across workspace members."""
        all_issues: list[tuple[str, dict[str, Any]]] = []
        for member in members:
            member_name = member.name
            issues = self._check_single(member, member_name=member_name)
            if isinstance(issues, list):
                for issue in issues:
                    all_issues.append((member_name, issue))

        issue_count = len(all_issues)
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
                "top_issues": [
                    _format_issue(issue, member=name) for name, issue in all_issues[:5]
                ],
            },
            fix_hint=("Run: deptry . to see details" if issue_count > 0 else None),
        )
