"""Unit tests for Practice Rules (pure, no I/O)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from axm_audit.models.results import Severity

if TYPE_CHECKING:
    from axm_audit.core.rules.practices.docstring_coverage import DocstringCoverageRule


class TestDocstringCoverageRuleUnit:
    """Tests for DocstringCoverageRule (pure)."""

    def test_rule_id_format(self) -> None:
        """Rule ID should be PRACTICE_DOCSTRING."""
        from axm_audit.core.rules.practices.docstring_coverage import (
            DocstringCoverageRule,
        )

        rule = DocstringCoverageRule()
        assert rule.rule_id == "PRACTICE_DOCSTRING"


class TestBareExceptRuleUnit:
    """Tests for BareExceptRule (pure)."""

    def test_rule_id_format(self) -> None:
        """Rule ID should be PRACTICE_BARE_EXCEPT."""
        from axm_audit.core.rules.practices.bare_except import BareExceptRule

        rule = BareExceptRule()
        assert rule.rule_id == "PRACTICE_BARE_EXCEPT"


class TestSecurityPatternRuleUnit:
    """Tests for SecurityPatternRule (pure)."""

    def test_rule_id_format(self) -> None:
        """Rule ID should be PRACTICE_SECURITY."""
        from axm_audit.core.rules.security import SecurityPatternRule

        rule = SecurityPatternRule()
        assert rule.rule_id == "PRACTICE_SECURITY"


class TestBlockingIORuleUnit:
    """Tests for BlockingIORule (pure)."""

    def test_rule_id_format(self) -> None:
        """Rule ID should be PRACTICE_BLOCKING_IO."""
        from axm_audit.core.rules.practices.blocking_io import BlockingIORule

        rule = BlockingIORule()
        assert rule.rule_id == "PRACTICE_BLOCKING_IO"


class TestTestMirrorRuleUnit:
    """Tests for TestMirrorRule (pure)."""

    def test_rule_id_format(self) -> None:
        """Rule ID should be PRACTICE_TEST_MIRROR."""
        from axm_audit.core.rules.practices.test_mirror import TestMirrorRule

        rule = TestMirrorRule()
        assert rule.rule_id == "PRACTICE_TEST_MIRROR"


class TestFormatAgentActionable:
    """Tests for format_agent surfacing details on passed checks."""

    def test_passed_with_missing_includes_details(self) -> None:
        """Passed check with missing docstrings includes full details."""
        from axm_audit.formatters import format_agent
        from axm_audit.models.results import AuditResult, CheckResult

        check = CheckResult(
            rule_id="PRACTICE_DOCSTRING",
            passed=True,
            message="Docstring coverage: 88% (7/8)",
            severity=Severity.INFO,
            details={
                "coverage": 0.88,
                "total": 8,
                "documented": 7,
                "missing": ["mod.py:foo"],
            },
            fix_hint="Add docstrings to public functions",
        )
        result = AuditResult(checks=[check])
        output = format_agent(result)

        # Passed entry should be a dict with details, not a plain string
        assert len(output["passed"]) == 1
        entry = output["passed"][0]
        assert isinstance(entry, dict)
        assert entry["details"]["missing"] == ["mod.py:foo"]

    def test_passed_clean_is_string(self) -> None:
        """Passed check with no actionable items stays as summary string."""
        from axm_audit.formatters import format_agent
        from axm_audit.models.results import AuditResult, CheckResult

        check = CheckResult(
            rule_id="QUALITY_TYPE",
            passed=True,
            message="Type score: 100/100",
            severity=Severity.INFO,
            score=100,
        )
        result = AuditResult(checks=[check])
        output = format_agent(result)

        assert len(output["passed"]) == 1
        assert isinstance(output["passed"][0], str)

    def test_passed_empty_missing_is_string(self) -> None:
        """Passed check with empty missing list stays as summary string."""
        from axm_audit.formatters import format_agent
        from axm_audit.models.results import AuditResult, CheckResult

        check = CheckResult(
            rule_id="PRACTICE_DOCSTRING",
            passed=True,
            message="Docstring coverage: 100% (8/8)",
            severity=Severity.INFO,
            details={"coverage": 1.0, "total": 8, "documented": 8, "missing": []},
        )
        result = AuditResult(checks=[check])
        output = format_agent(result)

        assert len(output["passed"]) == 1
        assert isinstance(output["passed"][0], str)


class TestDocstringTextRendering:
    """Tests for _build_result text= output (AXM-1395)."""

    @pytest.fixture
    def rule(self) -> DocstringCoverageRule:
        from axm_audit.core.rules.practices.docstring_coverage import (
            DocstringCoverageRule,
        )

        return DocstringCoverageRule()

    def test_docstring_text_with_missing(self, rule: DocstringCoverageRule) -> None:
        """Passed with 6 missing across 3 modules -> 3 grouped bullet lines."""
        missing = [
            "core.py:process_data",
            "core.py:validate_input",
            "utils.py:format_output",
            "utils.py:parse_config",
            "helpers.py:build_key",
            "helpers.py:load_data",
        ]
        result = rule._build_result(documented=44, missing=missing)

        assert result.passed is True
        assert result.text is not None
        lines = result.text.split("\n")
        assert len(lines) == 3
        for line in lines:
            assert line.startswith("     \u2022 ")
        assert "core.py: process_data, validate_input" in result.text
        assert "utils.py: format_output, parse_config" in result.text
        assert "helpers.py: build_key, load_data" in result.text
        # AC3: details dict unchanged
        assert result.details is not None
        assert result.details["missing"] == missing
        assert result.details["coverage"] == 0.88
        assert result.details["total"] == 50
        assert result.details["documented"] == 44
        assert result.score == 88

    def test_docstring_text_perfect(self, rule: DocstringCoverageRule) -> None:
        """100% coverage -> text is None."""
        result = rule._build_result(documented=10, missing=[])

        assert result.passed is True
        assert result.text is None
        # AC3: details dict unchanged
        assert result.details is not None
        assert result.details["missing"] == []
        assert result.score == 100

    def test_docstring_text_failed(self, rule: DocstringCoverageRule) -> None:
        """Below threshold, 12 missing across 4 files.

        Grouped bullets, passed False.
        """
        missing = [
            "mod_a.py:f1",
            "mod_a.py:f2",
            "mod_a.py:f3",
            "mod_b.py:f4",
            "mod_b.py:f5",
            "mod_b.py:f6",
            "mod_c.py:f7",
            "mod_c.py:f8",
            "mod_c.py:f9",
            "mod_d.py:f10",
            "mod_d.py:f11",
            "mod_d.py:f12",
        ]
        result = rule._build_result(documented=3, missing=missing)

        assert result.passed is False
        assert result.text is not None
        lines = result.text.split("\n")
        assert len(lines) == 4
        for line in lines:
            assert line.startswith("     \u2022 ")
        assert "mod_a.py: f1, f2, f3" in result.text
        assert "mod_b.py: f4, f5, f6" in result.text
        assert "mod_c.py: f7, f8, f9" in result.text
        assert "mod_d.py: f10, f11, f12" in result.text

    # --- Edge cases ---

    def test_docstring_text_single_file_single_missing(
        self, rule: DocstringCoverageRule
    ) -> None:
        """Single missing func in one file -> one bullet line."""
        result = rule._build_result(documented=9, missing=["file.py:func_name"])

        assert result.text is not None
        lines = result.text.split("\n")
        assert len(lines) == 1
        assert lines[0] == "     \u2022 file.py: func_name"

    def test_docstring_text_nested_path(self, rule: DocstringCoverageRule) -> None:
        """Nested path uses full relative path as grouping key."""
        missing = [
            "pkg/sub/module.py:func_a",
            "pkg/sub/module.py:func_b",
        ]
        result = rule._build_result(documented=8, missing=missing)

        assert result.text is not None
        lines = result.text.split("\n")
        assert len(lines) == 1
        assert "pkg/sub/module.py: func_a, func_b" in lines[0]
