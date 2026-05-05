"""Tests for rich CLI details, improvements section, and legacy removal."""

import pytest

from axm_audit.formatters import format_report
from axm_audit.models.results import AuditResult, CheckResult

# ── _format_check_details tests ──────────────────────────────────────


class TestFormatCheckDetails:
    """Tests for _format_check_details rendering."""

    def test_complexity_top_offenders(self) -> None:
        """Complexity details should list each offending function."""
        check = CheckResult(
            rule_id="QUALITY_COMPLEXITY",
            passed=False,
            message="Complexity score: 50/100",
            text="• foo.py:bar 15\n• baz.py:qux 12",
            details={
                "top_offenders": [
                    {"file": "foo.py", "function": "bar", "cc": 15},
                    {"file": "baz.py", "function": "qux", "cc": 12},
                ],
            },
        )
        report = format_report(AuditResult(checks=[check]))
        assert "     • foo.py:bar 15" in report
        assert "     • baz.py:qux 12" in report

    def test_security_top_issues(self) -> None:
        """Security details should list each issue with severity."""
        check = CheckResult(
            rule_id="QUALITY_SECURITY",
            passed=False,
            message="Security score: 50/100",
            text="• H B105 auth.py:42 Hardcoded password",
            details={
                "top_issues": [
                    {
                        "severity": "HIGH",
                        "code": "B105",
                        "message": "Hardcoded password",
                        "file": "auth.py",
                        "line": 42,
                    },
                ],
            },
        )
        report = format_report(AuditResult(checks=[check]))
        assert "     • H B105 auth.py:42 Hardcoded password" in report

    def test_deps_audit_top_vulns(self) -> None:
        """Dependency audit details should list vulnerable packages."""
        check = CheckResult(
            rule_id="DEPS_AUDIT",
            passed=False,
            message="2 vulnerable packages",
            text="    • requests==2.25.0\n    • pip==21.0",
            details={
                "top_vulns": [
                    {"name": "requests", "version": "2.25.0"},
                    {"name": "pip", "version": "21.0"},
                ],
            },
        )
        report = format_report(AuditResult(checks=[check]))
        assert "requests==2.25.0" in report
        assert "pip==21.0" in report

    def test_deps_hygiene_top_issues(self) -> None:
        """Dependency hygiene details should list issues."""
        check = CheckResult(
            rule_id="DEPS_HYGIENE",
            passed=False,
            message="3 issues",
            text="• DEP001 foo: missing dep",
            details={
                "top_issues": [
                    {"code": "DEP001", "module": "foo", "message": "missing"},
                ],
            },
        )
        report = format_report(AuditResult(checks=[check]))
        assert "     • DEP001 foo: missing dep" in report

    def test_details_works_for_passing_checks_with_low_score(self) -> None:
        """Passing checks with score<100 render details under Improvements."""
        check = CheckResult(
            rule_id="QUALITY_COMPLEXITY",
            passed=True,
            score=90,
            message="Complexity score: 90/100",
            text="• foo.py:bar 11",
            details={
                "top_offenders": [
                    {"file": "foo.py", "function": "bar", "cc": 11},
                ],
            },
        )
        report = format_report(AuditResult(checks=[check]))
        assert "Improvements" in report
        assert "     • foo.py:bar 11" in report

    def test_score_100_no_details(self) -> None:
        """Passing checks at score=100 should produce no bullet details."""
        check = CheckResult(
            rule_id="QUALITY_LINT",
            passed=True,
            message="OK",
            score=100,
        )
        report = format_report(AuditResult(checks=[check]))
        assert "•" not in report
        assert "Improvements" not in report

    def test_no_details_returns_empty(self) -> None:
        """Checks without text/details should produce no bullets."""
        check = CheckResult(
            rule_id="QUALITY_LINT",
            passed=True,
            message="OK",
        )
        report = format_report(AuditResult(checks=[check]))
        assert "•" not in report


# ── Improvements section tests ───────────────────────────────────────


class TestImprovementsSection:
    """Tests for the ⚠️ Improvements section in format_report."""

    def test_improvements_shown_when_score_below_100(self) -> None:
        """Report should have Improvements section for score < 100."""
        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="QUALITY_COMPLEXITY",
                    passed=True,
                    message="Complexity score: 90/100",
                    score=90,
                    details={
                        "top_offenders": [
                            {"file": "f.py", "function": "g", "cc": 11},
                        ],
                    },
                    fix_hint="Refactor complex functions",
                ),
            ]
        )
        report = format_report(result)
        assert "Improvements" in report
        assert "⚡" in report

    def test_improvements_shows_details(self) -> None:
        """Improvements section should show bullet-point details."""
        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="DEPS_AUDIT",
                    passed=True,
                    message="1 vulnerable package(s)",
                    text="    • pip==25.3",
                    score=85,
                    details={
                        "top_vulns": [
                            {"name": "pip", "version": "25.3"},
                        ],
                    },
                    fix_hint="Run: pip-audit --fix",
                ),
            ]
        )
        report = format_report(result)
        assert "•" in report
        assert "pip==25.3" in report

    def test_improvements_shows_tip(self) -> None:
        """Improvements section should show Tip from fix_hint."""
        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="QUALITY_COVERAGE",
                    passed=True,
                    message="Coverage: 89%",
                    score=88,
                    details={"coverage": 89.0},
                    fix_hint="Add tests for uncovered branches",
                ),
            ]
        )
        report = format_report(result)
        assert "Tip:" in report
        assert "Add tests" in report

    def test_no_improvements_at_100(self) -> None:
        """No improvements section when all scores are 100."""
        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="QUALITY_LINT",
                    passed=True,
                    message="OK",
                    score=100,
                ),
                CheckResult(
                    rule_id="QUALITY_TYPE",
                    passed=True,
                    message="OK",
                    score=100,
                ),
            ]
        )
        report = format_report(result)
        assert "Improvements" not in report
        assert "⚡" not in report


# ── format_report integration tests ─────────────────────────────────


class TestFormatReportRichOutput:
    """Tests for rich format_report output."""

    def test_report_shows_score_per_check(self) -> None:
        """Each check in category section should show score/100."""
        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="QUALITY_LINT",
                    passed=True,
                    message="Lint score: 100/100",
                    score=100,
                ),
                CheckResult(
                    rule_id="QUALITY_COMPLEXITY",
                    passed=False,
                    message="Complexity score: 50/100",
                    score=50,
                ),
            ]
        )
        report = format_report(result)
        assert "100/100" in report
        assert "50/100" in report

    def test_report_shows_details_in_failures(self) -> None:
        """Failure section should show contextual bullet points."""
        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="QUALITY_COMPLEXITY",
                    passed=False,
                    message="Complexity score: 50/100",
                    text="• foo.py:bar 15",
                    details={
                        "top_offenders": [
                            {"file": "foo.py", "function": "bar", "cc": 15},
                        ],
                    },
                    fix_hint="Refactor",
                ),
            ]
        )
        report = format_report(result)
        assert "•" in report
        assert "foo.py" in report
        assert "bar" in report
        assert "15" in report

    def test_report_no_details_for_perfect_passing_checks(self) -> None:
        """Passing checks at 100 should NOT have bullet-point details."""
        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="QUALITY_LINT",
                    passed=True,
                    message="OK",
                    score=100,
                ),
            ]
        )
        report = format_report(result)
        assert "•" not in report


# ── Legacy removal tests ────────────────────────────────────────────


class TestLegacyRemoval:
    """Tests that legacy structure rules are removed."""

    @pytest.mark.parametrize(
        "removed_prefix",
        ["FILE_EXISTS_", "DIR_EXISTS_"],
    )
    def test_legacy_existence_rules_removed(self, removed_prefix: str) -> None:
        """FILE_EXISTS_ and DIR_EXISTS_ rules should not be in the rule set."""
        from axm_audit.core.auditor import get_rules_for_category

        rules = get_rules_for_category(None)
        rule_ids = [r.rule_id for r in rules]
        assert not any(rid.startswith(removed_prefix) for rid in rule_ids)

    def test_pyproject_completeness_still_exists(self) -> None:
        """PyprojectCompletenessRule should still be registered."""
        from axm_audit.core.auditor import get_rules_for_category

        rules = get_rules_for_category(None)
        rule_ids = [r.rule_id for r in rules]
        assert "STRUCTURE_PYPROJECT" in rule_ids

    def test_valid_categories_count(self) -> None:
        """Should have 11 valid categories (aligned with scoring)."""
        from axm_audit.core.auditor import VALID_CATEGORIES

        assert len(VALID_CATEGORIES) == 11
        assert "structure" in VALID_CATEGORIES
        assert "test_quality" in VALID_CATEGORIES
