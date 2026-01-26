"""Tests for audit models."""

import pytest

class TestModels:
    """Test that audit models work correctly in axm-audit."""

    def test_audit_result_import(self):
        """Test that AuditResult can be imported."""
        from axm_audit.models import AuditResult
        assert AuditResult is not None

    def test_check_result_import(self):
        """Test that CheckResult can be imported."""
        from axm_audit.models import CheckResult
        assert CheckResult is not None

    def test_severity_import(self):
        """Test that Severity can be imported."""
        from axm_audit.models import Severity
        assert Severity is not None


class TestCheckResult:
    """Tests for CheckResult model."""

    def test_passed_check(self) -> None:
        """Passed check should have passed=True."""
        from axm_audit.models.results import CheckResult

        result = CheckResult(
            rule_id="FILE_EXISTS",
            passed=True,
            message="pyproject.toml exists",
        )
        assert result.passed is True
        assert result.rule_id == "FILE_EXISTS"

    def test_failed_check(self) -> None:
        """Failed check should have passed=False."""
        from axm_audit.models.results import CheckResult

        result = CheckResult(
            rule_id="FILE_EXISTS",
            passed=False,
            message="README.md not found",
        )
        assert result.passed is False

    def test_audit_result_creation(self):
        """Test creating an AuditResult instance."""
        from axm_audit.models import AuditResult, CheckResult
        
        check = CheckResult(rule_id="TEST", passed=True, message="Test")
        result = AuditResult(checks=[check])
        
        assert result.total == 1
        assert result.success is True

    def test_audit_result_failure(self) -> None:
        """Audit with some checks failed."""
        from axm_audit.models.results import AuditResult, CheckResult

        checks = [
            CheckResult(rule_id="F1", passed=True, message="OK"),
            CheckResult(rule_id="F2", passed=False, message="FAIL"),
        ]
        result = AuditResult(checks=checks)
        assert result.success is False
        assert result.total == 2
        assert result.failed == 1

    def test_json_serialization(self) -> None:
        """AuditResult should serialize to valid JSON for Agents."""
        import json
        from axm_audit.models.results import AuditResult, CheckResult

        result = AuditResult(
            checks=[CheckResult(rule_id="TEST", passed=True, message="OK")]
        )
        data = json.loads(result.model_dump_json())
        assert "checks" in data
        assert "success" in data
        assert data["success"] is True

    def test_audit_result_quality_score(self):
        """Test that quality scoring works."""
        from axm_audit.models import AuditResult, CheckResult
        
        checks = [
            CheckResult(
                rule_id="QUALITY_LINT",
                passed=True,
                message="Pass",
                details={"score": 90.0},
            ),
            CheckResult(
                rule_id="QUALITY_TYPE",
                passed=False,
                message="Fail",
                details={"score": 50.0},
            ),
        ]
        result = AuditResult(checks=checks)
        
        assert result.quality_score is not None
        assert 0 <= result.quality_score <= 100

    def test_audit_result_grade(self):
        """Test that letter grading works."""
        from axm_audit.models import AuditResult, CheckResult
        
        checks = [
            CheckResult(
                rule_id="QUALITY_LINT",
                passed=True,
                message="Pass",
                details={"score": 95.0},
            )
        ]
        result = AuditResult(checks=checks)
        
        assert result.grade in ["A", "B", "C", "D", "F"]
