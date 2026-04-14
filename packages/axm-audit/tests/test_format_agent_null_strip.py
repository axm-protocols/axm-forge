"""Tests for format_agent null-key stripping (AXM-1414)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from axm_audit.formatters import format_agent
from axm_audit.models.results import AuditResult, CheckResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def _make_result() -> Callable[..., AuditResult]:
    """Return a factory that wraps a single CheckResult in an AuditResult."""

    def _factory(**kwargs: Any) -> AuditResult:
        return AuditResult(checks=[CheckResult(**kwargs)])

    return _factory


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestFailedNoDetailsOmitsNullKeys:
    """Failed check with all optional fields None omits those keys."""

    def test_failed_no_details_omits_null_keys(
        self, _make_result: Callable[..., AuditResult]
    ) -> None:
        result = _make_result(
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
        self, _make_result: Callable[..., AuditResult]
    ) -> None:
        result = _make_result(
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
        assert failed["details"] == {"violations": ["E501"]}
        assert failed["fix_hint"] == "Run ruff --fix"
        assert failed["rule_id"] == "QUALITY_LINT"
        assert failed["message"] == "Lint failed"


class TestPassedActionableNoFixHint:
    """Passed actionable check omits fix_hint when None."""

    def test_passed_actionable_no_fix_hint(
        self, _make_result: Callable[..., AuditResult]
    ) -> None:
        result = _make_result(
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
        self, _make_result: Callable[..., AuditResult]
    ) -> None:
        result = _make_result(
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


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases for null-key stripping."""

    def test_all_keys_none_has_exactly_two_keys(
        self, _make_result: Callable[..., AuditResult]
    ) -> None:
        """Failed check with only rule_id + message -> dict has exactly 2 keys."""
        result = _make_result(
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
        self, _make_result: Callable[..., AuditResult]
    ) -> None:
        """Failed check with details but no text -> details present, text absent."""
        result = _make_result(
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
        self, _make_result: Callable[..., AuditResult]
    ) -> None:
        """Empty string fix_hint is falsy -> key omitted."""
        result = _make_result(
            rule_id="R1",
            passed=False,
            message="msg",
            text=None,
            details=None,
            fix_hint="",
        )
        output = format_agent(result)
        failed = output["failed"][0]
        assert "fix_hint" not in failed
