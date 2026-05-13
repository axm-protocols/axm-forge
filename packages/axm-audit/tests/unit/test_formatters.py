"""Tests for axm_audit.formatters."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pytest

from axm_audit.formatters import (
    format_agent,
    format_agent_text,
    format_json,
    format_report,
    format_test_quality_json,
    format_test_quality_text,
)
from axm_audit.models import AuditResult as AuditResultModels
from axm_audit.models import CheckResult as CheckResultModels
from axm_audit.models.results import AuditResult, CheckResult

# ---------------------------------------------------------------------------
# --- format_report / format_json / format_agent (original test_formatters) ---
# ---------------------------------------------------------------------------


class TestFormatReport:
    """Tests for format_report function."""

    def test_report_contains_score(self) -> None:
        """Report should display score and grade."""
        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="QUALITY_LINT",
                    passed=True,
                    message="Lint score: 100/100 (0 issues)",
                    score=100,
                    category="lint",
                ),
            ]
        )
        report = format_report(result)
        assert "Score:" in report

    def test_report_shows_pass_fail_icons(self) -> None:
        """Report should use ✅ for pass and ❌ for fail."""
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
                    passed=False,
                    message="FAIL",
                    score=0,
                ),
            ]
        )
        report = format_report(result)
        assert "✅" in report
        assert "❌" in report

    def test_format_report_shows_project_path(self) -> None:
        """Report header should display the actual project path."""
        result = AuditResult(
            project_path="/tmp/my-project",
            checks=[
                CheckResult(
                    rule_id="QUALITY_LINT",
                    passed=True,
                    message="OK",
                    score=100,
                ),
            ],
        )
        report = format_report(result)
        assert "/tmp/my-project" in report

    def test_format_report_no_checks(self) -> None:
        """Empty checks list should not crash, still shows path."""
        result = AuditResult(project_path="/tmp/p", checks=[])
        report = format_report(result)
        assert "/tmp/p" in report

    def test_format_report_no_path_fallback(self) -> None:
        """Missing project_path falls back to 'unknown'."""
        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="QUALITY_LINT",
                    passed=True,
                    message="OK",
                    score=100,
                ),
            ],
        )
        report = format_report(result)
        assert "unknown" in report

    def test_format_categories_uses_check_category(self) -> None:
        """Categories should group by check.category, not rule_id prefix."""
        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="QUALITY_LINT",
                    passed=True,
                    message="OK",
                    score=100,
                    category="lint",
                ),
                CheckResult(
                    rule_id="QUALITY_TYPE",
                    passed=True,
                    message="OK",
                    score=100,
                    category="type",
                ),
            ]
        )
        report = format_report(result)
        assert "lint" in report
        assert "type" in report

    def test_format_categories_none_category_grouped_as_other(self) -> None:
        """Check with category=None should be grouped under 'other'."""
        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="CUSTOM_CHECK",
                    passed=True,
                    message="OK",
                    category=None,
                ),
            ]
        )
        report = format_report(result)
        assert "other" in report


class TestFormatJson:
    """Tests for format_json function."""

    def test_json_has_required_keys(self) -> None:
        """JSON output should have score, grade, checks."""
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
        data = format_json(result)
        assert "score" in data
        assert "grade" in data
        assert "checks" in data


class TestFormatAgent:
    """Tests for format_agent function."""

    def test_format_agent_all_passed(self) -> None:
        """All passing checks → failed=[], passed has 1-line strings."""
        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="QUALITY_LINT",
                    passed=True,
                    message="Lint score: 100/100",
                    score=100,
                ),
                CheckResult(
                    rule_id="QUALITY_TYPE",
                    passed=True,
                    message="Type score: 100/100",
                    score=100,
                ),
            ]
        )
        output = format_agent(result)
        assert output["failed"] == []
        assert len(output["passed"]) == 2
        assert all(isinstance(p, str) for p in output["passed"])

    def test_format_agent_mixed(self) -> None:
        """Failed items have full detail, passed items are 1-liners."""
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
                    passed=False,
                    message="Type errors found",
                    score=75,
                    details={"error_count": 5},
                    fix_hint="Add type hints",
                ),
            ]
        )
        output = format_agent(result)
        assert len(output["passed"]) == 1
        assert len(output["failed"]) == 1
        assert "details" in output["failed"][0]
        assert "fix_hint" in output["failed"][0]
        assert output["failed"][0]["fix_hint"] == "Add type hints"

    def test_format_agent_no_score(self) -> None:
        """No crash when quality_score is None."""
        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="FILE_EXISTS_README.md",
                    passed=True,
                    message="exists",
                ),
            ]
        )
        output = format_agent(result)
        assert output["score"] is None
        assert output["grade"] is None

    def test_format_agent_has_required_keys(self) -> None:
        """Agent output must have score, grade, passed, failed."""
        result = AuditResult(
            checks=[
                CheckResult(rule_id="R1", passed=True, message="OK"),
            ]
        )
        output = format_agent(result)
        assert set(output.keys()) == {"score", "grade", "passed", "failed"}

    def test_passed_complexity_includes_top_offenders(self) -> None:
        """Passed complexity check with top_offenders should expose details dict."""
        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="QUALITY_COMPLEXITY",
                    passed=True,
                    message="Complexity score: 90/100",
                    details={
                        "top_offenders": [
                            {"file": "foo.py", "function": "bar", "cc": 12},
                        ],
                    },
                    category="complexity",
                ),
            ]
        )
        output = format_agent(result)
        assert len(output["passed"]) == 1
        entry = output["passed"][0]
        assert isinstance(entry, dict)
        assert "details" in entry
        assert entry["details"]["top_offenders"] == [
            {"file": "foo.py", "function": "bar", "cc": 12},
        ]

    def test_passed_complexity_no_offenders_is_string(self) -> None:
        """Passed complexity with empty top_offenders → string-only, no details."""
        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="QUALITY_COMPLEXITY",
                    passed=True,
                    message="Complexity score: 100/100",
                    details={
                        "top_offenders": [],
                    },
                    category="complexity",
                ),
            ]
        )
        output = format_agent(result)
        assert len(output["passed"]) == 1
        assert isinstance(output["passed"][0], str)

    def test_passed_complexity_multiple_offenders_exposes_details(self) -> None:
        """Passed complexity with 1+ offenders → details dict with offenders."""
        offenders = [
            {"file": "a.py", "function": "func_a", "cc": 15},
            {"file": "b.py", "function": "func_b", "cc": 11},
        ]
        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="QUALITY_COMPLEXITY",
                    passed=True,
                    message="Complexity score: 90/100",
                    details={
                        "top_offenders": offenders,
                    },
                    category="complexity",
                ),
            ]
        )
        output = format_agent(result)
        entry = output["passed"][0]
        assert isinstance(entry, dict)
        assert entry["details"]["top_offenders"] == offenders


# ---------------------------------------------------------------------------
# --- format_agent: drop_nulls (test_format_agent_drop_nulls.py) ---
# ---------------------------------------------------------------------------


@dataclass
class _DropNullsCheckResult:
    rule_id: str
    message: str
    passed: bool
    text: str | None = None
    details: dict[str, Any] | None = None
    fix_hint: str | None = None
    score: int | None = None


@dataclass
class _DropNullsAuditResult:
    quality_score: int = 100
    grade: str = "A"
    checks: list[_DropNullsCheckResult] = field(default_factory=list)


class TestFormatAgentDropNulls:
    def test_format_agent_drops_null_keys_failed(self) -> None:
        """Failed dict with all nullable fields None has only rule_id + message."""
        result = _DropNullsAuditResult(
            checks=[
                _DropNullsCheckResult(
                    rule_id="R001",
                    message="something failed",
                    passed=False,
                    details=None,
                    text=None,
                    fix_hint=None,
                ),
            ],
        )
        output = format_agent(result)
        failed = output["failed"]
        assert len(failed) == 1
        assert set(failed[0].keys()) == {"rule_id", "message"}

    def test_format_agent_keeps_non_null_keys_failed(self) -> None:
        """Failed dict with text and details — only text emitted (XOR)."""
        result = _DropNullsAuditResult(
            checks=[
                _DropNullsCheckResult(
                    rule_id="R002",
                    message="check failed",
                    passed=False,
                    score=50,
                    text="• issue",
                    fix_hint="fix it",
                ),
            ],
        )
        output = format_agent(result)
        failed = output["failed"]
        assert len(failed) == 1
        assert set(failed[0].keys()) == {
            "rule_id",
            "message",
            "text",
            "fix_hint",
        }

    def test_format_agent_drops_null_fix_hint_passed(self) -> None:
        """Passed actionable dict with fix_hint=None omits fix_hint key."""
        result = _DropNullsAuditResult(
            checks=[
                _DropNullsCheckResult(
                    rule_id="R003",
                    message="has missing items",
                    passed=True,
                    details={"missing": ["x"]},
                    fix_hint=None,
                ),
            ],
        )
        output = format_agent(result)
        passed = output["passed"]
        assert len(passed) == 1
        assert isinstance(passed[0], dict)
        assert "fix_hint" not in passed[0]

    def test_format_agent_all_keys_present_failed(self) -> None:
        """When all fields are populated, text wins — details excluded (XOR)."""
        result = _DropNullsAuditResult(
            checks=[
                _DropNullsCheckResult(
                    rule_id="R010",
                    message="full check",
                    passed=False,
                    text="detail text",
                    score=80,
                    fix_hint="try this",
                ),
            ],
        )
        output = format_agent(result)
        failed = output["failed"]
        assert set(failed[0].keys()) == {
            "rule_id",
            "message",
            "text",
            "fix_hint",
        }

    def test_format_agent_only_nullables_null_failed(self) -> None:
        """Failed dict with all nullable fields None yields only rule_id + message."""
        result = _DropNullsAuditResult(
            checks=[
                _DropNullsCheckResult(
                    rule_id="R011",
                    message="minimal",
                    passed=False,
                    details=None,
                    text=None,
                    fix_hint=None,
                ),
            ],
        )
        output = format_agent(result)
        failed = output["failed"]
        assert set(failed[0].keys()) == {"rule_id", "message"}

    def test_format_agent_mixed_nulls_failed(self) -> None:
        """Failed dict with text=None but details and fix_hint present has 4 keys."""
        result = _DropNullsAuditResult(
            checks=[
                _DropNullsCheckResult(
                    rule_id="R012",
                    message="mixed",
                    passed=False,
                    text=None,
                    details={"issues": ["a"]},
                    fix_hint="do something",
                ),
            ],
        )
        output = format_agent(result)
        failed = output["failed"]
        assert set(failed[0].keys()) == {"rule_id", "message", "details", "fix_hint"}
        assert "text" not in failed[0]


# ---------------------------------------------------------------------------
# --- format_agent: null_strip (test_format_agent_null_strip.py) ---
# ---------------------------------------------------------------------------


@pytest.fixture()
def _null_strip_make_result() -> Callable[..., AuditResult]:
    """Return a factory that wraps a single CheckResult in an AuditResult."""

    def _factory(**kwargs: Any) -> AuditResult:
        return AuditResult(checks=[CheckResult(**kwargs)])

    return _factory


class TestFailedNoDetailsOmitsNullKeys:
    """Failed check with all optional fields None omits those keys."""

    def test_failed_no_details_omits_null_keys(
        self, _null_strip_make_result: Callable[..., AuditResult]
    ) -> None:
        result = _null_strip_make_result(
            rule_id="QUALITY_LINT",
            passed=False,
            message="Lint failed",
            text=None,
            details=None,
            fix_hint=None,
        )
        output = format_agent(result)
        failed = output["failed"][0]

        assert "text" not in failed
        assert "details" not in failed
        assert "fix_hint" not in failed
        assert failed["rule_id"] == "QUALITY_LINT"
        assert failed["message"] == "Lint failed"


class TestFailedWithDetailsIncludesKeys:
    """Failed check with all optional fields populated includes them."""

    def test_failed_with_details_includes_keys(
        self, _null_strip_make_result: Callable[..., AuditResult]
    ) -> None:
        result = _null_strip_make_result(
            rule_id="QUALITY_LINT",
            passed=False,
            message="Lint failed",
            text="ruff output here",
            details={"violations": ["E501"]},
            fix_hint="Run ruff --fix",
        )
        output = format_agent(result)
        failed = output["failed"][0]

        assert failed["text"] == "ruff output here"
        assert "details" not in failed
        assert failed["fix_hint"] == "Run ruff --fix"
        assert failed["rule_id"] == "QUALITY_LINT"
        assert failed["message"] == "Lint failed"


class TestPassedActionableNoFixHint:
    """Passed actionable check omits fix_hint when None."""

    def test_passed_actionable_no_fix_hint(
        self, _null_strip_make_result: Callable[..., AuditResult]
    ) -> None:
        result = _null_strip_make_result(
            rule_id="QUALITY_DOCS",
            passed=True,
            message="Missing docstrings",
            details={"missing": ["foo", "bar"]},
            fix_hint=None,
        )
        output = format_agent(result)
        passed_entry = output["passed"][0]

        assert isinstance(passed_entry, dict)
        assert "fix_hint" not in passed_entry
        assert passed_entry["rule_id"] == "QUALITY_DOCS"
        assert passed_entry["details"] == {"missing": ["foo", "bar"]}


class TestPassedActionableWithFixHint:
    """Passed actionable check includes fix_hint when present."""

    def test_passed_actionable_with_fix_hint(
        self, _null_strip_make_result: Callable[..., AuditResult]
    ) -> None:
        result = _null_strip_make_result(
            rule_id="QUALITY_DOCS",
            passed=True,
            message="Missing docstrings",
            details={"missing": ["foo"]},
            fix_hint="Add docstrings to foo",
        )
        output = format_agent(result)
        passed_entry = output["passed"][0]

        assert isinstance(passed_entry, dict)
        assert passed_entry["fix_hint"] == "Add docstrings to foo"


class TestNullStripEdgeCases:
    """Edge cases for null-key stripping."""

    def test_all_keys_none_has_exactly_two_keys(
        self, _null_strip_make_result: Callable[..., AuditResult]
    ) -> None:
        """Failed check with only rule_id + message -> dict has exactly 2 keys."""
        result = _null_strip_make_result(
            rule_id="STRUCT_1",
            passed=False,
            message="structure issue",
            text=None,
            details=None,
            fix_hint=None,
        )
        output = format_agent(result)
        failed = output["failed"][0]
        assert set(failed.keys()) == {"rule_id", "message"}

    def test_mixed_none_and_non_none(
        self, _null_strip_make_result: Callable[..., AuditResult]
    ) -> None:
        """Failed check with details but no text -> details present, text absent."""
        result = _null_strip_make_result(
            rule_id="R1",
            passed=False,
            message="msg",
            text=None,
            details={"x": 1},
            fix_hint=None,
        )
        output = format_agent(result)
        failed = output["failed"][0]

        assert "details" in failed
        assert failed["details"] == {"x": 1}
        assert "text" not in failed
        assert "fix_hint" not in failed

    def test_empty_string_treated_as_falsy(
        self, _null_strip_make_result: Callable[..., AuditResult]
    ) -> None:
        """Empty string fix_hint is preserved (not None)."""
        result = _null_strip_make_result(
            rule_id="R1",
            passed=False,
            message="msg",
            text=None,
            details=None,
            fix_hint="",
        )
        output = format_agent(result)
        failed = output["failed"][0]
        assert failed["fix_hint"] == ""


# ---------------------------------------------------------------------------
# --- format_agent + format_agent_text (test_format_agent_text.py) ---
# ---------------------------------------------------------------------------


def _agent_text_make_result(checks: list[CheckResultModels]) -> AuditResultModels:
    return AuditResultModels(checks=checks)


class TestFormatAgentText:
    def test_format_agent_failed_with_text_includes_both(self) -> None:
        """When a failed check has text and details, only text is emitted."""
        check = CheckResultModels(
            rule_id="R001",
            message="some issue",
            passed=False,
            text="• file:1: issue",
            details={"locations": ["file:1"]},
            fix_hint="fix it",
        )
        out = format_agent(_agent_text_make_result([check]))
        failed = out["failed"]
        assert len(failed) == 1
        assert failed[0]["text"] == "• file:1: issue"
        assert "details" not in failed[0]

    def test_format_agent_failed_without_text_includes_details(self) -> None:
        """When a failed check has text=None, details key must be present."""
        check = CheckResultModels(
            rule_id="R002",
            message="another issue",
            passed=False,
            text=None,
            details={"locations": ["file:2"]},
            fix_hint=None,
        )
        out = format_agent(_agent_text_make_result([check]))
        failed = out["failed"]
        assert len(failed) == 1
        assert "details" in failed[0]
        assert failed[0]["details"] == {"locations": ["file:2"]}

    def test_format_agent_passed_actionable_unchanged(self) -> None:
        """Passed checks with actionable detail still include details."""
        check = CheckResultModels(
            rule_id="R003",
            message="missing docstrings",
            passed=True,
            text=None,
            details={"missing": ["foo", "bar"]},
            fix_hint=None,
        )
        out = format_agent(_agent_text_make_result([check]))
        passed_dicts = [p for p in out["passed"] if isinstance(p, dict)]
        assert len(passed_dicts) == 1
        assert "details" in passed_dicts[0]
        assert passed_dicts[0]["details"] == {"missing": ["foo", "bar"]}

    def test_format_agent_failed_empty_text_excluded(self) -> None:
        """Empty string text is falsy — details present, text absent."""
        check = CheckResultModels(
            rule_id="R004",
            message="edge case",
            passed=False,
            text="",
            details={"issues": ["a"]},
            fix_hint=None,
        )
        out = format_agent(_agent_text_make_result([check]))
        failed = out["failed"]
        assert len(failed) == 1
        assert "details" in failed[0]
        assert failed[0]["details"] == {"issues": ["a"]}
        assert "text" not in failed[0]

    def test_format_agent_failed_both_none_no_crash(self) -> None:
        """Both text and details None — must not crash."""
        check = CheckResultModels(
            rule_id="R005",
            message="both none",
            passed=False,
            text=None,
            details=None,
            fix_hint=None,
        )
        out = format_agent(_agent_text_make_result([check]))
        failed = out["failed"]
        assert len(failed) == 1
        assert failed[0]["rule_id"] == "R005"


@pytest.fixture()
def full_audit_data() -> dict[str, Any]:
    """3 passed strings + 1 failed dict with text."""
    return {
        "score": 85,
        "grade": "B",
        "passed": [
            "QUALITY_LINT: Lint score: 100/100 (0 issues)",
            "QUALITY_TYPES: Type coverage OK",
            "QUALITY_SECURITY: No issues found",
        ],
        "failed": [
            {
                "rule_id": "QUALITY_COMPLEXITY",
                "message": "3 functions exceed CC threshold",
                "text": "src/mod.py:10 func_a CC=15\nsrc/mod.py:30 func_b CC=12",
                "fix_hint": "Extract helpers to reduce CC",
            },
        ],
    }


def test_format_agent_text_full_audit(full_audit_data: dict[str, Any]) -> None:
    text = format_agent_text(full_audit_data)
    lines = text.splitlines()

    header = lines[0]
    assert "3 pass" in header
    assert "1 fail" in header

    assert "QUALITY_LINT" in text
    assert "QUALITY_TYPES" in text
    assert "QUALITY_SECURITY" in text
    assert "✓" in text

    assert "QUALITY_COMPLEXITY" in text
    assert "✗" in text
    assert "3 functions exceed CC threshold" in text
    assert "src/mod.py:10 func_a CC=15" in text
    assert "Extract helpers to reduce CC" in text


def test_format_agent_text_category_all_pass() -> None:
    data = {
        "score": 100,
        "grade": "A",
        "passed": [
            "QUALITY_LINT: Lint score: 100/100 (0 issues)",
            "QUALITY_STYLE: Style OK",
        ],
        "failed": [],
    }
    text = format_agent_text(data, category="lint")
    assert text.startswith("audit lint")
    assert "2 pass" in text
    assert "0 fail" in text
    assert "✗" not in text


def test_format_agent_text_category_all_fail() -> None:
    data = {
        "score": 0,
        "grade": "F",
        "passed": [],
        "failed": [
            {
                "rule_id": "QUALITY_TYPES",
                "message": "Type errors found",
                "text": "src/a.py:1 error: Missing return type",
            },
        ],
    }
    text = format_agent_text(data, category="type")
    assert text.startswith("audit type")
    assert "0 pass" in text
    assert "1 fail" in text
    assert "✓" not in text


def test_format_agent_text_none_score() -> None:
    data = {
        "score": None,
        "grade": None,
        "passed": ["STRUCT_LAYOUT: OK"],
        "failed": [],
    }
    text = format_agent_text(data)
    assert "None" not in text
    assert "1 pass" in text


def test_format_agent_text_actionable_passed() -> None:
    data = {
        "score": 90,
        "grade": "A",
        "passed": [
            {
                "rule_id": "QUALITY_DOCS",
                "message": "Docstring coverage 80%",
                "details": {"missing": ["src/a.py::foo"]},
            },
        ],
        "failed": [],
    }
    text = format_agent_text(data)
    assert "QUALITY_DOCS" in text
    assert "✓" in text


def test_format_agent_text_failed_no_text_uses_details() -> None:
    data = {
        "score": 50,
        "grade": "D",
        "passed": [],
        "failed": [
            {
                "rule_id": "QUALITY_SECURITY",
                "message": "Security issues found",
                "details": {"issues": ["S101 assert used", "S105 hardcoded password"]},
            },
        ],
    }
    text = format_agent_text(data)
    assert "QUALITY_SECURITY" in text
    assert "issues" in text


def test_format_agent_text_empty_checks() -> None:
    data: dict[str, Any] = {
        "score": None,
        "grade": None,
        "passed": [],
        "failed": [],
    }
    text = format_agent_text(data)
    assert "0 pass" in text
    assert "0 fail" in text


def test_format_agent_text_long_passed_list() -> None:
    passed = [f"RULE_{i:02d}: Check {i} passed" for i in range(22)]
    data = {
        "score": 95,
        "grade": "A",
        "passed": passed,
        "failed": [],
    }
    text = format_agent_text(data)
    check_lines = [ln for ln in text.splitlines() if "✓" in ln]
    for ln in check_lines:
        rule_ids = [tok for tok in ln.split() if tok.startswith("RULE_")]
        assert len(rule_ids) <= 5
    assert "22 pass" in text


def test_format_agent_text_failed_no_fix_hint() -> None:
    data = {
        "score": 60,
        "grade": "C",
        "passed": [],
        "failed": [
            {
                "rule_id": "QUALITY_TESTS",
                "message": "Coverage below threshold",
                "text": "Coverage: 45%",
            },
        ],
    }
    text = format_agent_text(data)
    assert "QUALITY_TESTS" in text
    assert "fix:" not in text.lower()


def test_format_agent_text_failed_multiline_text() -> None:
    multiline = "\n".join(f"src/file{i}.py:1 error {i}" for i in range(6))
    data = {
        "score": 30,
        "grade": "F",
        "passed": [],
        "failed": [
            {
                "rule_id": "QUALITY_LINT",
                "message": "Many lint errors",
                "text": multiline,
                "fix_hint": "Run ruff --fix",
            },
        ],
    }
    text = format_agent_text(data)
    for i in range(6):
        assert f"src/file{i}.py:1 error {i}" in text


# ---------------------------------------------------------------------------
# --- format_agent_text: structure (test_format_agent_text_structure.py) ---
# ---------------------------------------------------------------------------


def test_passed_chunked_5_per_line() -> None:
    rule_ids = [f"R{i:02d}" for i in range(12)]
    data = {
        "score": 100,
        "grade": "A",
        "passed": [{"rule_id": rid} for rid in rule_ids],
        "failed": [],
    }

    text = format_agent_text(data)
    check_lines = [line for line in text.splitlines() if line.startswith("✓ ")]

    assert len(check_lines) == 3
    assert check_lines[0] == "✓ " + " ".join(rule_ids[0:5])
    assert check_lines[1] == "✓ " + " ".join(rule_ids[5:10])
    assert check_lines[2] == "✓ " + " ".join(rule_ids[10:12])


def test_section_order_text_meta_fix() -> None:
    data = {
        "score": 50,
        "grade": "C",
        "passed": [],
        "failed": [
            {
                "rule_id": "X01",
                "message": "failure",
                "text": "line-A\nline-B",
                "metadata": {
                    "verdicts": [
                        {
                            "verdict": "FLAKY",
                            "test": "t1",
                            "file": "f.py",
                            "line": 10,
                        }
                    ],
                },
                "fix_hint": "do the thing",
            }
        ],
    }

    lines = format_agent_text(data).splitlines()
    indented = [line for line in lines if line.startswith("  ")]

    text_a = indented.index("  line-A")
    text_b = indented.index("  line-B")
    verdict_idx = next(
        i for i, line in enumerate(indented) if line.startswith("  [FLAKY]")
    )
    fix_idx = indented.index("  fix: do the thing")

    assert text_a < text_b < verdict_idx < fix_idx


# ---------------------------------------------------------------------------
# --- format_agent: xor (test_format_agent_xor.py) ---
# ---------------------------------------------------------------------------


def _xor_make_result(*checks: CheckResultModels) -> AuditResultModels:
    return AuditResultModels(checks=list(checks))


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            {
                "rule_id": "R001",
                "passed": False,
                "bucket": "failed",
                "text": "• issue",
                "details": {"items": [1, 2]},
                "expected_key": "text",
                "expected_value": "• issue",
            },
            id="failed_with_text",
        ),
        pytest.param(
            {
                "rule_id": "R002",
                "passed": False,
                "bucket": "failed",
                "text": None,
                "details": {"items": [1, 2]},
                "expected_key": "details",
                "expected_value": {"items": [1, 2]},
            },
            id="failed_without_text",
        ),
        pytest.param(
            {
                "rule_id": "R003",
                "passed": True,
                "bucket": "passed",
                "text": "• item",
                "details": {"missing": ["a", "b"]},
                "expected_key": "text",
                "expected_value": "• item",
            },
            id="passed_actionable_with_text",
        ),
        pytest.param(
            {
                "rule_id": "R004",
                "passed": True,
                "bucket": "passed",
                "text": None,
                "details": {"missing": ["a", "b"]},
                "expected_key": "details",
                "expected_value": {"missing": ["a", "b"]},
            },
            id="passed_actionable_without_text",
        ),
    ],
)
def test_format_agent_text_details_xor(case: dict[str, Any]) -> None:
    cr = CheckResultModels(
        rule_id=case["rule_id"],
        message="msg",
        passed=case["passed"],
        text=case["text"],
        details=case["details"],
        fix_hint="fix",
    )
    out = format_agent(_xor_make_result(cr))
    entry = out[case["bucket"]][0]
    assert isinstance(entry, dict)
    expected_key = case["expected_key"]
    other = "details" if expected_key == "text" else "text"
    assert expected_key in entry
    assert entry[expected_key] == case["expected_value"]
    assert other not in entry


def test_format_agent_failed_empty_text_preserved() -> None:
    """Empty string text is falsy - falls back to details, text omitted."""
    cr = CheckResultModels(
        rule_id="R005",
        message="edge empty",
        passed=False,
        text="",
        details={"items": [1]},
        fix_hint="fix",
    )
    out = format_agent(_xor_make_result(cr))
    entry = out["failed"][0]
    assert "details" in entry
    assert entry["details"] == {"items": [1]}
    assert "text" not in entry


def test_format_agent_failed_both_none() -> None:
    """Both text and details None - both dropped after AXM-1410."""
    cr = CheckResultModels(
        rule_id="R006",
        message="both none",
        passed=False,
        text=None,
        details=None,
        fix_hint="fix",
    )
    out = format_agent(_xor_make_result(cr))
    entry = out["failed"][0]
    assert "details" not in entry
    assert "text" not in entry
    assert set(entry.keys()) == {"rule_id", "message", "fix_hint"}


# ---------------------------------------------------------------------------
# --- format_agent: xor_passed (test_format_agent_xor_passed.py) ---
# ---------------------------------------------------------------------------


def _xor_passed_make_result(*checks: CheckResult) -> AuditResult:
    return AuditResult(checks=list(checks))


def test_format_agent_passed_actionable_text_excludes_details() -> None:
    """Passed check with truthy text should emit text only, not details."""
    cr = CheckResult(
        rule_id="R1",
        passed=True,
        message="ok",
        text="• item",
        details={"missing": ["a"]},
    )
    out = format_agent(_xor_passed_make_result(cr))
    entry = out["passed"][0]
    assert isinstance(entry, dict)
    assert entry["text"] == "• item"
    assert "details" not in entry


def test_format_agent_passed_actionable_no_text_includes_details() -> None:
    """Passed check with text=None should emit details as fallback."""
    cr = CheckResult(
        rule_id="R1",
        passed=True,
        message="ok",
        text=None,
        details={"missing": ["a"]},
    )
    out = format_agent(_xor_passed_make_result(cr))
    entry = out["passed"][0]
    assert isinstance(entry, dict)
    assert entry["details"] == {"missing": ["a"]}
    assert "text" not in entry


def test_format_agent_passed_actionable_empty_text_uses_details() -> None:
    """Empty string text is falsy — should emit details, not text."""
    cr = CheckResult(
        rule_id="R1",
        passed=True,
        message="ok",
        text="",
        details={"missing": ["a"]},
    )
    out = format_agent(_xor_passed_make_result(cr))
    entry = out["passed"][0]
    assert isinstance(entry, dict)
    assert "details" in entry
    assert "text" not in entry


def test_format_agent_passed_non_actionable_string_form() -> None:
    """Passed check with text but no actionable details stays as string."""
    cr = CheckResult(
        rule_id="R1",
        passed=True,
        message="info",
        text="• info",
        details=None,
    )
    out = format_agent(_xor_passed_make_result(cr))
    entry = out["passed"][0]
    assert isinstance(entry, str)
    assert "R1" in entry


# ---------------------------------------------------------------------------
# --- format_test_quality_text (test_format_test_quality_text.py) ---
# ---------------------------------------------------------------------------


@pytest.fixture
def result_one_per_section() -> AuditResult:
    """AuditResult exercising every branch of ``format_test_quality_text``."""
    return AuditResult(
        checks=[
            CheckResult(
                rule_id="QUALITY_TEST_PRIVATE_IMPORTS",
                passed=False,
                message="private import",
                metadata={
                    "private_import_violations": [
                        {
                            "file": "tests/unit/foo.py",
                            "line": 10,
                            "symbol": "mypkg._private",
                        }
                    ],
                },
            ),
            CheckResult(
                rule_id="QUALITY_TEST_PYRAMID",
                passed=False,
                message="pyramid mismatch",
                metadata={
                    "pyramid_mismatches": [
                        {
                            "test": "tests/unit/test_bar.py::test_x",
                            "current_dir": "unit",
                            "detected_level": "integration",
                        }
                    ],
                },
            ),
            CheckResult(
                rule_id="QUALITY_TEST_DUPLICATES",
                passed=False,
                message="duplicates",
                metadata={
                    "clusters": [
                        {
                            "signal": "call_sig",
                            "members": [
                                {
                                    "test": "test_a",
                                    "file": "tests/unit/a.py",
                                    "line": 5,
                                }
                            ],
                        }
                    ],
                },
            ),
            CheckResult(
                rule_id="QUALITY_TEST_TAUTOLOGY",
                passed=False,
                message="tautology",
                metadata={
                    "verdicts": [
                        {
                            "verdict": "TAUTOLOGY",
                            "test": "test_c",
                            "file": "tests/unit/c.py",
                            "line": 15,
                        }
                    ],
                },
            ),
        ]
    )


SNAPSHOT = (
    "Private imports:\n"
    "  tests/unit/foo.py:10  mypkg._private\n"
    "\n"
    "Pyramid:\n"
    "  tests/unit/test_bar.py::test_x  unit -> integration  [MISMATCH]\n"
    "\n"
    "Duplicates:\n"
    "  [call_sig]\n"
    "    tests/unit/a.py:5  test_a\n"
    "\n"
    "Tautologies:\n"
    "  [TAUTOLOGY] test_c  tests/unit/c.py:15"
)


def test_format_test_quality_text_byte_identical_after_refactor(
    result_one_per_section: AuditResult,
) -> None:
    """Full-mode output must byte-match the pre-refactor snapshot (AC2)."""
    assert format_test_quality_text(result_one_per_section) == SNAPSHOT


def test_legacy_details_findings_shape() -> None:
    """Legacy ``details.findings`` payload must populate the private section (AC3)."""
    result = AuditResult(
        checks=[
            CheckResult(
                rule_id="QUALITY_TEST_PRIVATE_IMPORTS",
                passed=False,
                message="private import",
                details={
                    "findings": [
                        {
                            "test_file": "tests/unit/legacy.py",
                            "line": 7,
                            "private_symbol": "mypkg._secret",
                        }
                    ],
                },
            ),
        ]
    )

    payload = format_test_quality_json(result)

    assert payload["private_import_violations"] == [
        {
            "file": "tests/unit/legacy.py",
            "line": 7,
            "symbol": "mypkg._secret",
        }
    ]


def test_clusters_member_key_tolerance() -> None:
    """Clusters with ``members``/``tests`` keys must yield identical output (AC3)."""
    member = {"test": "test_x", "file": "tests/unit/x.py", "line": 3}
    result = AuditResult(
        checks=[
            CheckResult(
                rule_id="QUALITY_TEST_DUPLICATES",
                passed=False,
                message="members key",
                metadata={
                    "clusters": [{"signal": "sig_a", "members": [member]}],
                },
            ),
            CheckResult(
                rule_id="QUALITY_TEST_DUPLICATES",
                passed=False,
                message="tests key",
                metadata={
                    "clusters": [{"signal": "sig_b", "tests": [member]}],
                },
            ),
        ]
    )

    payload = format_test_quality_json(result)

    assert [c["members"] for c in payload["clusters"]] == [
        [member],
        [member],
    ]
    assert [c["signal"] for c in payload["clusters"]] == ["sig_a", "sig_b"]


# ---------------------------------------------------------------------------
# --- format_agent_text: metadata (test_agent_text_metadata.py) ---
# ---------------------------------------------------------------------------


def test_format_agent_text_with_verdicts_no_keyerror() -> None:
    data = {
        "score": 80,
        "grade": "B",
        "passed": [],
        "failed": [
            {
                "rule_id": "tautologies",
                "message": "found",
                "metadata": {
                    "verdicts": [
                        {
                            "test": "step_n2_import_smoke",
                            "verdict": "DELETE",
                            "file": "t.py",
                            "line": 1,
                        },
                    ],
                },
            },
        ],
    }
    out = format_agent_text(data)
    assert isinstance(out, str)
    assert out


def test_format_agent_text_with_clusters_no_keyerror() -> None:
    data = {
        "score": 80,
        "grade": "B",
        "passed": [],
        "failed": [
            {
                "rule_id": "duplicates",
                "message": "found",
                "metadata": {
                    "clusters": [
                        {
                            "signal": "signal1_call_assert",
                            "members": [
                                {"test": "t1", "file": "f.py", "line": 1},
                            ],
                        },
                    ],
                    "buckets": {"signal1_call_assert": 1},
                },
            },
        ],
    }
    out = format_agent_text(data)
    assert isinstance(out, str)
    assert out


def test_format_agent_text_backward_compat_no_metadata() -> None:
    data = {
        "score": 100,
        "grade": "A",
        "passed": [{"rule_id": "r1"}],
        "failed": [],
    }
    out = format_agent_text(data)
    assert isinstance(out, str)
    assert "r1" in out


# ---------------------------------------------------------------------------
# --- format_agent: xor semantics (merged from test_format_agent_xor_semantics.py) ---
# ---------------------------------------------------------------------------


def _xor_semantics_make_result(*checks: CheckResultModels) -> AuditResultModels:
    return AuditResultModels(checks=list(checks))


@pytest.mark.parametrize(
    ("text", "details", "expected_text", "expected_details"),
    [
        pytest.param(
            "• issue",
            {"items": [1]},
            "• issue",
            None,
            id="text_wins_over_details",
        ),
        pytest.param(
            None,
            {"items": [1]},
            None,
            {"items": [1]},
            id="none_text_falls_back_to_details",
        ),
        pytest.param(
            "",
            {"items": [1]},
            None,
            {"items": [1]},
            id="empty_text_falls_back_to_details",
        ),
        pytest.param(None, None, None, None, id="both_none_emits_neither"),
        pytest.param("• issue", None, "• issue", None, id="text_only"),
        pytest.param(None, {}, None, {}, id="empty_details_dict_still_emitted"),
    ],
)
def test_format_agent_text_details_xor_semantics(
    text: str | None,
    details: dict[str, Any] | None,
    expected_text: str | None,
    expected_details: dict[str, Any] | None,
) -> None:
    """format_agent emits text XOR details on failed checks (text wins when truthy)."""
    cr = CheckResultModels(
        rule_id="R", message="m", passed=False, text=text, details=details
    )
    entry = format_agent(_xor_semantics_make_result(cr))["failed"][0]

    if expected_text is None:
        assert "text" not in entry
    else:
        assert entry["text"] == expected_text

    if expected_details is None:
        assert "details" not in entry
    else:
        assert entry["details"] == expected_details


# ---------------------------------------------------------------------------
# --- format_agent: metadata propagation (merged from test_formatters_metadata.py) ---
# ---------------------------------------------------------------------------

from axm_audit.core.rules.test_quality.duplicate_tests import (  # noqa: E402
    DuplicateTestsCheckResult,
)
from axm_audit.core.rules.test_quality.tautology import (  # noqa: E402
    TautologyCheckResult,
)


def _metadata_audit(checks: list[CheckResult]) -> AuditResult:
    return AuditResult(checks=checks)


def test_format_agent_failed_includes_metadata_when_present() -> None:
    verdicts = [
        {
            "file": "tests/unit/test_x.py",
            "test": "test_x",
            "line": 3,
            "pattern": "assert True",
            "verdict": "tautology",
            "reason": "trivially true",
        }
    ]
    check = TautologyCheckResult(
        rule_id="TEST_QUALITY_TAUTOLOGY",
        passed=False,
        message="1 tautological test",
        metadata={"verdicts": verdicts},
    )
    out = format_agent(_metadata_audit([check]))
    assert out["failed"][0]["metadata"]["verdicts"] == verdicts


def test_format_agent_passed_includes_metadata_when_present() -> None:
    check = TautologyCheckResult(
        rule_id="TEST_QUALITY_TAUTOLOGY",
        passed=True,
        message="ok",
        metadata={"verdicts": [{"info": 1}]},
    )
    out = format_agent(_metadata_audit([check]))
    entry = out["passed"][0]
    assert isinstance(entry, dict)
    assert entry["metadata"] == {"verdicts": [{"info": 1}]}


def test_format_agent_omits_metadata_when_empty() -> None:
    empty_meta = TautologyCheckResult(
        rule_id="TEST_QUALITY_TAUTOLOGY",
        passed=False,
        message="failed",
        metadata={},
    )
    no_meta = CheckResult(
        rule_id="OTHER",
        passed=False,
        message="failed",
    )
    out = format_agent(_metadata_audit([empty_meta, no_meta]))
    for entry in out["failed"]:
        assert "metadata" not in entry


def test_format_agent_clusters_metadata_propagates() -> None:
    clusters = [{"id": 0, "members": ["a", "b"]}]
    check = DuplicateTestsCheckResult(
        rule_id="TEST_QUALITY_DUPLICATE_TESTS",
        passed=False,
        message="1 duplicate cluster",
        metadata={"clusters": clusters},
    )
    out = format_agent(_metadata_audit([check]))
    assert out["failed"][0]["metadata"]["clusters"] == clusters


# ---------------------------------------------------------------------------
# --- merged from test_rich_output.py (rich CLI details + improvements) ---
# ---------------------------------------------------------------------------


class TestFormatCheckDetails:
    """Tests for _format_check_details rendering."""

    def test_complexity_top_offenders(self) -> None:
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
        check = CheckResult(
            rule_id="QUALITY_LINT",
            passed=True,
            message="OK",
        )
        report = format_report(AuditResult(checks=[check]))
        assert "•" not in report


class TestImprovementsSection:
    """Tests for the Improvements section in format_report."""

    def test_improvements_shown_when_score_below_100(self) -> None:
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


class TestFormatReportRichOutput:
    """Tests for rich format_report output."""

    def test_report_shows_score_per_check(self) -> None:
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


class TestLegacyRemoval:
    """Tests that legacy structure rules are removed."""

    @pytest.mark.parametrize(
        "removed_prefix",
        ["FILE_EXISTS_", "DIR_EXISTS_"],
    )
    def test_legacy_existence_rules_removed(self, removed_prefix: str) -> None:
        from axm_audit.core.auditor import get_rules_for_category

        rules = get_rules_for_category(None)
        rule_ids = [r.rule_id for r in rules]
        assert not any(rid.startswith(removed_prefix) for rid in rule_ids)

    def test_pyproject_completeness_still_exists(self) -> None:
        from axm_audit.core.auditor import get_rules_for_category

        rules = get_rules_for_category(None)
        rule_ids = [r.rule_id for r in rules]
        assert "STRUCTURE_PYPROJECT" in rule_ids

    def test_valid_categories_count(self) -> None:
        from axm_audit.core.auditor import VALID_CATEGORIES

        assert len(VALID_CATEGORIES) == 11
        assert "structure" in VALID_CATEGORIES
        assert "test_quality" in VALID_CATEGORIES


def test_format_agent_text_unchanged_for_tautology() -> None:
    verdicts = [
        {
            "file": "tests/unit/test_x.py",
            "test": "test_x",
            "line": 3,
            "pattern": "assert True",
            "verdict": "tautology",
            "reason": "trivially true",
        }
    ]
    dup = DuplicateTestsCheckResult(
        rule_id="TEST_QUALITY_DUPLICATE_TESTS",
        passed=False,
        message="dup",
        metadata={"clusters": [{"id": 0, "members": ["a", "b"]}]},
    )
    taut = TautologyCheckResult(
        rule_id="TEST_QUALITY_TAUTOLOGY",
        passed=False,
        message="taut",
        metadata={"verdicts": verdicts},
    )
    result = _metadata_audit([dup, taut])
    text = format_agent_text(format_agent(result))
    assert isinstance(text, str)
    assert text
