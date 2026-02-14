"""Tests for Dependency Rules — DependencyAuditRule + DependencyHygieneRule."""

from pathlib import Path
from unittest.mock import patch


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
        assert result.details is not None
        assert result.details["score"] == 0
        assert result.fix_hint is not None

    def test_rule_id(self) -> None:
        """Rule ID should be DEPS_HYGIENE."""
        from axm_audit.core.rules.dependencies import DependencyHygieneRule

        assert DependencyHygieneRule().rule_id == "DEPS_HYGIENE"
