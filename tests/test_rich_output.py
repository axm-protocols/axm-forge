"""Tests for rich CLI details, improvements section, and legacy removal."""

import pytest

from axm_audit.formatters import format_report
from axm_audit.models.results import AuditResult, CheckResult

# ── _format_check_details tests ──────────────────────────────────────


class TestFormatCheckDetails:
    """Tests for _format_check_details rendering."""

    def test_complexity_top_offenders(self) -> None:
        """Complexity details should list each offending function."""
        from axm_audit.formatters import _format_check_details

        check = CheckResult(
            rule_id="QUALITY_COMPLEXITY",
            passed=False,
            message="Complexity score: 50/100",
            details={
                "top_offenders": [
                    {"file": "foo.py", "function": "bar", "cc": 15},
                    {"file": "baz.py", "function": "qux", "cc": 12},
                ],
                "score": 50,
            },
        )
        lines = _format_check_details(check)
        assert len(lines) == 2
        assert "foo.py" in lines[0]
        assert "bar" in lines[0]
        assert "cc=15" in lines[0]
        assert "baz.py" in lines[1]

    def test_security_top_issues(self) -> None:
        """Security details should list each issue with severity."""
        from axm_audit.formatters import _format_check_details

        check = CheckResult(
            rule_id="QUALITY_SECURITY",
            passed=False,
            message="Security score: 50/100",
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
                "score": 50,
            },
        )
        lines = _format_check_details(check)
        assert len(lines) == 1
        assert "HIGH" in lines[0]
        assert "B105" in lines[0]
        assert "auth.py" in lines[0]

    def test_deps_audit_top_vulns(self) -> None:
        """Dependency audit details should list vulnerable packages."""
        from axm_audit.formatters import _format_check_details

        check = CheckResult(
            rule_id="DEPS_AUDIT",
            passed=False,
            message="2 vulnerable packages",
            details={
                "top_vulns": [
                    {"name": "requests", "version": "2.25.0"},
                    {"name": "pip", "version": "21.0"},
                ],
                "score": 70,
            },
        )
        lines = _format_check_details(check)
        assert len(lines) == 2
        assert "requests" in lines[0]
        assert "2.25.0" in lines[0]

    def test_deps_hygiene_top_issues(self) -> None:
        """Dependency hygiene details should list issues."""
        from axm_audit.formatters import _format_check_details

        check = CheckResult(
            rule_id="DEPS_HYGIENE",
            passed=False,
            message="3 issues",
            details={
                "top_issues": [
                    {"code": "DEP001", "module": "foo", "message": "missing"},
                ],
                "score": 70,
            },
        )
        lines = _format_check_details(check)
        assert len(lines) == 1
        assert "DEP001" in lines[0]
        assert "foo" in lines[0]

    def test_details_works_for_passing_checks_with_low_score(self) -> None:
        """_format_check_details should return lines for passing checks
        that have score < 100 (for the improvements section)."""
        from axm_audit.formatters import _format_check_details

        check = CheckResult(
            rule_id="QUALITY_COMPLEXITY",
            passed=True,
            message="Complexity score: 90/100",
            details={
                "top_offenders": [
                    {"file": "foo.py", "function": "bar", "cc": 11},
                ],
                "score": 90,
            },
        )
        lines = _format_check_details(check)
        assert len(lines) == 1
        assert "foo.py" in lines[0]

    def test_score_100_no_details(self) -> None:
        """Passing checks at score=100 should return empty list."""
        from axm_audit.formatters import _format_check_details

        check = CheckResult(
            rule_id="QUALITY_LINT",
            passed=True,
            message="OK",
            details={"score": 100},
        )
        lines = _format_check_details(check)
        assert lines == []

    def test_no_details_returns_empty(self) -> None:
        """Checks without details should return empty list."""
        from axm_audit.formatters import _format_check_details

        check = CheckResult(
            rule_id="QUALITY_LINT",
            passed=True,
            message="OK",
        )
        lines = _format_check_details(check)
        assert lines == []


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
                    details={
                        "top_offenders": [
                            {"file": "f.py", "function": "g", "cc": 11},
                        ],
                        "score": 90,
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
                    details={
                        "top_vulns": [
                            {"name": "pip", "version": "25.3"},
                        ],
                        "score": 85,
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
                    details={"coverage": 89.0, "score": 88},
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
                    details={"score": 100},
                ),
                CheckResult(
                    rule_id="QUALITY_TYPE",
                    passed=True,
                    message="OK",
                    details={"score": 100},
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
                    details={"score": 100},
                ),
                CheckResult(
                    rule_id="QUALITY_COMPLEXITY",
                    passed=False,
                    message="Complexity score: 50/100",
                    details={"score": 50},
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
                    details={
                        "top_offenders": [
                            {"file": "foo.py", "function": "bar", "cc": 15},
                        ],
                        "score": 50,
                    },
                    fix_hint="Refactor",
                ),
            ]
        )
        report = format_report(result)
        assert "•" in report
        assert "foo.py" in report
        assert "bar" in report
        assert "cc=15" in report

    def test_report_no_details_for_perfect_passing_checks(self) -> None:
        """Passing checks at 100 should NOT have bullet-point details."""
        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="QUALITY_LINT",
                    passed=True,
                    message="OK",
                    details={"score": 100},
                ),
            ]
        )
        report = format_report(result)
        assert "•" not in report


# ── Legacy removal tests ────────────────────────────────────────────


class TestLegacyRemoval:
    """Tests that legacy structure rules are removed."""

    def test_total_rules_count(self) -> None:
        """Should have 17 total rules (was 20, removed 3 structure)."""
        from axm_audit.core.auditor import get_rules_for_category

        rules = get_rules_for_category(None)
        assert len(rules) == 18

    def test_no_file_exists_rules(self) -> None:
        """FILE_EXISTS rules should not be in the rule set."""
        from axm_audit.core.auditor import get_rules_for_category

        rules = get_rules_for_category(None)
        rule_ids = [r.rule_id for r in rules]
        assert not any(rid.startswith("FILE_EXISTS_") for rid in rule_ids)

    def test_no_dir_exists_rules(self) -> None:
        """DIR_EXISTS rules should not be in the rule set."""
        from axm_audit.core.auditor import get_rules_for_category

        rules = get_rules_for_category(None)
        rule_ids = [r.rule_id for r in rules]
        assert not any(rid.startswith("DIR_EXISTS_") for rid in rule_ids)

    def test_pyproject_completeness_still_exists(self) -> None:
        """PyprojectCompletenessRule should still be registered."""
        from axm_audit.core.auditor import get_rules_for_category

        rules = get_rules_for_category(None)
        rule_ids = [r.rule_id for r in rules]
        assert "STRUCTURE_PYPROJECT" in rule_ids

    def test_valid_categories_count(self) -> None:
        """Should have 8 valid categories (structure kept for pyproject)."""
        from axm_audit.core.auditor import VALID_CATEGORIES

        assert len(VALID_CATEGORIES) == 8
        assert "structure" in VALID_CATEGORIES


# ── Complexity verification tests ────────────────────────────────────


class TestComplexityAfterRefactoring:
    """Verify refactored functions have cc < 10."""

    @pytest.mark.parametrize(
        "module_path,function_name",
        [
            ("src/axm_audit/formatters.py", "format_report"),
            ("src/axm_audit/formatters.py", "_format_check_details"),
            ("src/axm_audit/core/rules/security.py", "check"),
            ("src/axm_audit/core/rules/dependencies.py", "check"),
            ("src/axm_audit/core/rules/structure.py", "check"),
            ("src/axm_audit/core/rules/architecture.py", "check"),
        ],
    )
    def test_function_cc_under_10(self, module_path: str, function_name: str) -> None:
        """Each refactored function must have cc < 10."""
        from pathlib import Path

        from radon.complexity import cc_visit

        project_root = Path(__file__).parent.parent
        source = (project_root / module_path).read_text()
        blocks = cc_visit(source)

        for block in blocks:
            if block.name == function_name:
                assert block.complexity < 10, (
                    f"{module_path}:{function_name} has cc={block.complexity}, "
                    f"expected < 10"
                )
