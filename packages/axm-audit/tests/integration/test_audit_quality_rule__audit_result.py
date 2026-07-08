"""Tests for AuditQualityRule witness rule."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from axm_audit.models.results import AuditResult, CheckResult, Severity
from axm_audit.witnesses.audit_quality import AuditQualityRule


def _check(
    rule_id: str,
    passed: bool,
    message: str = "ok",
    *,
    details: dict[str, object] | None = None,
    fix_hint: str | None = None,
) -> CheckResult:
    """Helper to build CheckResult."""
    return CheckResult(
        rule_id=rule_id,
        passed=passed,
        message=message,
        severity=Severity.ERROR if not passed else Severity.INFO,
        details=details,
        fix_hint=fix_hint,
    )


class TestAuditQualityAllPass:
    """AC1: lint and type both pass."""

    @patch("axm_audit.witnesses.audit_quality.audit_project")
    def test_audit_quality_all_pass(
        self, mock_audit: MagicMock, tmp_path: Path
    ) -> None:
        mock_audit.return_value = AuditResult(
            checks=[
                _check("ruff", True, "No lint issues"),
            ]
        )

        rule = AuditQualityRule(
            categories=["lint", "type"],
            working_dir=str(tmp_path),
        )
        result = rule.validate("")

        assert result.passed is True
        assert result.feedback is None
        assert mock_audit.call_count == 2


class TestAuditQualityLintFails:
    """AC1+AC2: lint fails, type still runs, feedback is structured."""

    @patch("axm_audit.witnesses.audit_quality.audit_project")
    def test_audit_quality_lint_fails(
        self, mock_audit: MagicMock, tmp_path: Path
    ) -> None:
        lint_result = AuditResult(
            checks=[
                _check(
                    "ruff-F841",
                    False,
                    "Local variable 'x' is assigned but never used",
                    details={"file": "src/foo.py", "line": 10, "code": "F841"},
                    fix_hint="Remove unused variable 'x'",
                ),
                _check(
                    "ruff-E501",
                    False,
                    "Line too long",
                    details={"file": "src/bar.py", "line": 5, "code": "E501"},
                    fix_hint="Break line",
                ),
            ]
        )
        type_result = AuditResult(
            checks=[
                _check("mypy", True, "No type errors"),
            ]
        )
        mock_audit.side_effect = [lint_result, type_result]

        rule = AuditQualityRule(
            categories=["lint", "type"],
            working_dir=str(tmp_path),
        )
        result = rule.validate("")

        assert result.passed is False
        assert result.feedback is not None
        assert "2 violation(s)" in result.feedback.what
        # Both categories ran
        assert mock_audit.call_count == 2


class TestAuditQualityTypeFails:
    """AC1: type fails independently."""

    @patch("axm_audit.witnesses.audit_quality.audit_project")
    def test_audit_quality_type_fails(
        self, mock_audit: MagicMock, tmp_path: Path
    ) -> None:
        lint_result = AuditResult(
            checks=[
                _check("ruff", True, "Clean"),
            ]
        )
        type_result = AuditResult(
            checks=[
                _check(
                    "mypy-arg-type",
                    False,
                    "Incompatible type",
                    details={"file": "src/a.py", "line": 1},
                ),
                _check(
                    "mypy-return",
                    False,
                    "Missing return",
                    details={"file": "src/b.py", "line": 2},
                ),
                _check(
                    "mypy-attr",
                    False,
                    "Has no attribute",
                    details={"file": "src/c.py", "line": 3},
                ),
            ]
        )
        mock_audit.side_effect = [lint_result, type_result]

        rule = AuditQualityRule(
            categories=["lint", "type"],
            working_dir=str(tmp_path),
        )
        result = rule.validate("")

        assert result.passed is False
        assert result.feedback is not None
        assert "3 violation(s)" in result.feedback.what


class TestAuditQualityBothFail:
    """AC1: both fail — no short-circuit, all errors aggregated."""

    @patch("axm_audit.witnesses.audit_quality.audit_project")
    def test_audit_quality_both_fail(
        self, mock_audit: MagicMock, tmp_path: Path
    ) -> None:
        lint_result = AuditResult(
            checks=[
                _check(
                    "ruff-F841",
                    False,
                    "Unused var",
                    details={"file": "src/x.py", "line": 1},
                ),
            ]
        )
        type_result = AuditResult(
            checks=[
                _check(
                    "mypy-1",
                    False,
                    "Type error 1",
                    details={"file": "src/y.py", "line": 2},
                ),
                _check(
                    "mypy-2",
                    False,
                    "Type error 2",
                    details={"file": "src/z.py", "line": 3},
                ),
            ]
        )
        mock_audit.side_effect = [lint_result, type_result]

        rule = AuditQualityRule(
            categories=["lint", "type"],
            working_dir=str(tmp_path),
        )
        result = rule.validate("")

        assert result.passed is False
        assert result.feedback is not None
        # 1 lint + 2 type = 3 total
        assert "3 violation(s)" in result.feedback.what
        assert mock_audit.call_count == 2


class TestFeedbackFormatAgentFriendly:
    """AC2: feedback contains structured dict with rule_id, file, line, message."""

    @patch("axm_audit.witnesses.audit_quality.audit_project")
    def test_feedback_format_agent_friendly(
        self, mock_audit: MagicMock, tmp_path: Path
    ) -> None:
        mock_audit.return_value = AuditResult(
            checks=[
                _check(
                    "ruff-F841",
                    False,
                    "Local variable 'x' is assigned but never used",
                    details={"file": "src/foo.py", "line": 10, "code": "F841"},
                    fix_hint="Remove unused variable 'x'",
                ),
            ]
        )

        rule = AuditQualityRule(
            categories=["lint"],
            working_dir=str(tmp_path),
        )
        result = rule.validate("")

        assert result.passed is False
        assert result.feedback is not None

        # why contains structured JSON
        failed_items = json.loads(result.feedback.why)
        assert len(failed_items) == 1
        item = failed_items[0]
        assert item["rule_id"] == "ruff-F841"
        assert item["details"]["file"] == "src/foo.py"
        assert item["details"]["line"] == 10
        assert item["message"] == "Local variable 'x' is assigned but never used"

        # metadata also has audit output
        assert "audit" in result.metadata
        assert result.metadata["audit"]["failed"]


class TestUnknownCategoryIsRed:
    """A config with an unknown category MUST fail loud, never pass green.

    Regression: the witness used to silently skip categories outside its
    private 5-category whitelist and, when the survivor set emptied, return
    ``WitnessResult.success()`` — a quality gate passing green having
    audited nothing. An unknown category is now a hard RED config error.
    """

    @patch("axm_audit.witnesses.audit_quality.audit_project")
    def test_unknown_category_fails_loud_before_auditing(
        self, mock_audit: MagicMock, tmp_path: Path
    ) -> None:
        mock_audit.return_value = AuditResult(
            checks=[
                _check("ruff", True, "Clean"),
            ]
        )

        rule = AuditQualityRule(
            categories=["lint", "unknown"],
            working_dir=str(tmp_path),
        )
        result = rule.validate("")

        assert result.passed is False
        assert result.feedback is not None
        assert "Unknown audit category" in result.feedback.what
        assert "unknown" in result.feedback.what
        # Fail-loud happens BEFORE any audit runs: nothing is executed when
        # the config itself is invalid.
        mock_audit.assert_not_called()


class TestWorkingDirFromKwargs:
    """working_dir from kwargs overrides instance attribute."""

    @patch("axm_audit.witnesses.audit_quality.audit_project")
    def test_working_dir_from_kwargs(
        self, mock_audit: MagicMock, tmp_path: Path
    ) -> None:
        mock_audit.return_value = AuditResult(
            checks=[
                _check("ruff", True, "Clean"),
            ]
        )

        rule = AuditQualityRule(
            categories=["lint"],
            working_dir="/nonexistent",  # would fail
        )
        # But kwargs override
        result = rule.validate("", working_dir=str(tmp_path))

        assert result.passed is True
