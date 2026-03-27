"""Tests for Dependency Rules — DependencyAuditRule + DependencyHygieneRule."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from axm_audit.models.results import Severity


class TestDependencyAuditRule:
    """Tests for DependencyAuditRule (pip-audit integration)."""

    def test_clean_project_passes(self, tmp_path: Path) -> None:
        """No vulnerabilities → score=100, passed=True."""
        from axm_audit.core.rules.dependencies import DependencyAuditRule

        mock_result = type(
            "Result", (), {"stdout": "[]", "stderr": "", "returncode": 0}
        )()

        rule = DependencyAuditRule()
        with patch("subprocess.run", return_value=mock_result):
            result = rule.check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["score"] == 100

    def test_vulnerabilities_reduce_score(self, tmp_path: Path) -> None:
        """CVEs should reduce score: high=-15, medium=-5."""
        import json

        from axm_audit.core.rules.dependencies import DependencyAuditRule

        vulns = [
            {
                "name": "pkg1",
                "version": "1.0",
                "fix_versions": ["1.1"],
                "aliases": ["CVE-2025-001"],
                "vulns": [{"id": "CVE-2025-001", "fix_versions": ["1.1"]}],
            },
            {
                "name": "pkg2",
                "version": "2.0",
                "fix_versions": ["2.1"],
                "aliases": ["CVE-2025-002"],
                "vulns": [{"id": "CVE-2025-002", "fix_versions": ["2.1"]}],
            },
        ]
        mock_result = type(
            "Result",
            (),
            {"stdout": json.dumps(vulns), "stderr": "", "returncode": 1},
        )()

        rule = DependencyAuditRule()
        with patch("subprocess.run", return_value=mock_result):
            result = rule.check(tmp_path)

        assert result.passed is False
        assert result.details is not None
        assert result.details["score"] < 100
        assert result.details["vuln_count"] == 2

    def test_tool_not_found(self, tmp_path: Path) -> None:
        """pip-audit not installed → score=0, fix_hint."""
        from axm_audit.core.rules.dependencies import DependencyAuditRule

        rule = DependencyAuditRule()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = rule.check(tmp_path)

        assert result.passed is False
        assert result.details is not None
        assert result.details["score"] == 0
        assert result.fix_hint is not None

    def test_rule_id(self) -> None:
        """Rule ID should be DEPS_AUDIT."""
        from axm_audit.core.rules.dependencies import DependencyAuditRule

        assert DependencyAuditRule().rule_id == "DEPS_AUDIT"

    def test_pip_audit_crash_not_false_positive(self, tmp_path: Path) -> None:
        """pip-audit crash (non-zero rc, empty stdout) must NOT pass."""
        from axm_audit.core.rules.dependencies import DependencyAuditRule

        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = "pip-audit: internal error"
        mock_result.returncode = 2

        rule = DependencyAuditRule()
        with patch("subprocess.run", return_value=mock_result):
            result = rule.check(tmp_path)

        assert not result.passed
        assert "pip-audit failed" in result.message
        assert "rc=2" in result.message
        assert result.severity == Severity.ERROR
        assert result.details is not None
        assert result.details["score"] == 0


class TestDependencyAuditRuleEnriched:
    """Tests for CVE IDs and fix versions in DEPS_AUDIT output (AXM-861)."""

    def _make_pip_audit_result(self, data: list[Any] | dict[str, Any]) -> object:
        """Helper: build a mock subprocess result from pip-audit JSON."""
        import json

        return type(
            "Result",
            (),
            {"stdout": json.dumps(data), "stderr": "", "returncode": 1},
        )()

    def test_vuln_ids_included(self, tmp_path: Path) -> None:
        """top_vulns entries must contain vuln_ids with the CVE ID."""
        from axm_audit.core.rules.dependencies import DependencyAuditRule

        data = [
            {
                "name": "requests",
                "version": "2.28.0",
                "vulns": [{"id": "CVE-2023-32681", "fix_versions": ["2.31.0"]}],
            },
        ]
        mock_result = self._make_pip_audit_result(data)

        rule = DependencyAuditRule()
        with patch("subprocess.run", return_value=mock_result):
            result = rule.check(tmp_path)

        assert result.details is not None
        top = result.details["top_vulns"][0]
        assert "vuln_ids" in top
        assert "CVE-2023-32681" in top["vuln_ids"]

    def test_fix_versions_included(self, tmp_path: Path) -> None:
        """top_vulns entries must list fix_versions."""
        from axm_audit.core.rules.dependencies import DependencyAuditRule

        data = [
            {
                "name": "requests",
                "version": "2.28.0",
                "vulns": [{"id": "CVE-2023-32681", "fix_versions": ["2.31.0"]}],
            },
        ]
        mock_result = self._make_pip_audit_result(data)

        rule = DependencyAuditRule()
        with patch("subprocess.run", return_value=mock_result):
            result = rule.check(tmp_path)

        assert result.details is not None
        top = result.details["top_vulns"][0]
        assert "fix_versions" in top
        assert "2.31.0" in top["fix_versions"]

    def test_no_fix_version_available(self, tmp_path: Path) -> None:
        """When fix_versions is empty, top_vulns entry has fix_versions=[]."""
        from axm_audit.core.rules.dependencies import DependencyAuditRule

        data = [
            {
                "name": "numpy",
                "version": "1.23.0",
                "vulns": [{"id": "CVE-2024-00001", "fix_versions": []}],
            },
        ]
        mock_result = self._make_pip_audit_result(data)

        rule = DependencyAuditRule()
        with patch("subprocess.run", return_value=mock_result):
            result = rule.check(tmp_path)

        assert result.details is not None
        top = result.details["top_vulns"][0]
        assert top["fix_versions"] == []

    def test_multiple_vulns_per_package(self, tmp_path: Path) -> None:
        """Package with 2+ vulns → vuln_ids aggregates all IDs."""
        from axm_audit.core.rules.dependencies import DependencyAuditRule

        data = [
            {
                "name": "django",
                "version": "3.2.0",
                "vulns": [
                    {"id": "CVE-2023-001", "fix_versions": ["3.2.19"]},
                    {"id": "CVE-2023-002", "fix_versions": ["3.2.20"]},
                ],
            },
        ]
        mock_result = self._make_pip_audit_result(data)

        rule = DependencyAuditRule()
        with patch("subprocess.run", return_value=mock_result):
            result = rule.check(tmp_path)

        assert result.details is not None
        top = result.details["top_vulns"][0]
        assert "CVE-2023-001" in top["vuln_ids"]
        assert "CVE-2023-002" in top["vuln_ids"]

    def test_missing_fix_versions_key(self, tmp_path: Path) -> None:
        """Older pip-audit format without fix_versions → default to []."""
        from axm_audit.core.rules.dependencies import DependencyAuditRule

        data = [
            {
                "name": "urllib3",
                "version": "1.26.0",
                "vulns": [{"id": "CVE-2024-99999"}],
            },
        ]
        mock_result = self._make_pip_audit_result(data)

        rule = DependencyAuditRule()
        with patch("subprocess.run", return_value=mock_result):
            result = rule.check(tmp_path)

        assert result.details is not None
        top = result.details["top_vulns"][0]
        assert top["fix_versions"] == []

    def test_empty_vulns_excluded(self, tmp_path: Path) -> None:
        """Package with empty vulns list is excluded from top_vulns (unchanged)."""
        from axm_audit.core.rules.dependencies import DependencyAuditRule

        data = [
            {"name": "safe-pkg", "version": "1.0.0", "vulns": []},
            {
                "name": "bad-pkg",
                "version": "0.9.0",
                "vulns": [{"id": "CVE-2025-111", "fix_versions": ["1.0.0"]}],
            },
        ]
        mock_result = self._make_pip_audit_result(data)

        rule = DependencyAuditRule()
        with patch("subprocess.run", return_value=mock_result):
            result = rule.check(tmp_path)

        assert result.details is not None
        assert result.details["vuln_count"] == 1
        names = [v["name"] for v in result.details["top_vulns"]]
        assert "safe-pkg" not in names
        assert "bad-pkg" in names


class TestDependencyHygieneRule:
    """Tests for DependencyHygieneRule (deptry integration)."""

    def test_clean_project_passes(self, tmp_path: Path) -> None:
        """No issues → score=100, passed=True."""
        from axm_audit.core.rules.dependencies import DependencyHygieneRule

        rule = DependencyHygieneRule()
        with patch(
            "axm_audit.core.rules.dependencies._run_deptry",
            return_value=[],
        ):
            result = rule.check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["score"] == 100

    def test_issues_reduce_score(self, tmp_path: Path) -> None:
        """Dependency issues should reduce score by 10 each."""
        from axm_audit.core.rules.dependencies import DependencyHygieneRule

        issues = [
            {"error_code": "DEP001", "module": "foo", "message": "unused"},
            {"error_code": "DEP002", "module": "bar", "message": "missing"},
            {"error_code": "DEP003", "module": "baz", "message": "transitive"},
        ]

        rule = DependencyHygieneRule()
        with patch(
            "axm_audit.core.rules.dependencies._run_deptry",
            return_value=issues,
        ):
            result = rule.check(tmp_path)

        assert result.passed is False
        assert result.details is not None
        assert result.details["score"] == 70  # 100 - 3*10
        assert result.details["issue_count"] == 3

    def test_tool_not_found(self, tmp_path: Path) -> None:
        """deptry not installed → score=0, fix_hint."""
        from axm_audit.core.rules.dependencies import DependencyHygieneRule

        rule = DependencyHygieneRule()
        with patch(
            "axm_audit.core.rules.dependencies._run_deptry",
            side_effect=FileNotFoundError,
        ):
            result = rule.check(tmp_path)

        assert result.passed is False
        assert "deptry not available" in result.message
        assert result.details is not None
        assert result.details["score"] == 0
        assert result.fix_hint is not None

    def test_rule_id(self) -> None:
        """Rule ID should be DEPS_HYGIENE."""
        from axm_audit.core.rules.dependencies import DependencyHygieneRule

        assert DependencyHygieneRule().rule_id == "DEPS_HYGIENE"

    def test_deptry_crash_not_false_positive(self, tmp_path: Path) -> None:
        """deptry crash (RuntimeError) must NOT produce false positive."""
        from axm_audit.core.rules.dependencies import DependencyHygieneRule

        rule = DependencyHygieneRule()
        with patch(
            "axm_audit.core.rules.dependencies._run_deptry",
            side_effect=RuntimeError("deptry failed (rc=1): segfault"),
        ):
            result = rule.check(tmp_path)

        assert not result.passed
        assert "deptry failed" in result.message
        assert result.severity == Severity.ERROR
        assert result.details is not None
        assert result.details["score"] == 0
