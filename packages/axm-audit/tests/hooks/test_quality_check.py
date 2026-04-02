from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from axm_audit.hooks.quality_check import QualityCheckHook


@pytest.fixture
def hook() -> QualityCheckHook:
    return QualityCheckHook()


@pytest.fixture
def context(tmp_path: Path) -> dict[str, str]:
    return {"working_dir": str(tmp_path)}


def _make_audit_result(checks: list[MagicMock] | None = None) -> MagicMock:
    """Build a mock AuditResult with given checks."""
    result = MagicMock()
    result.checks = checks or []
    return result


def _make_check(
    *,
    passed: bool,
    rule_id: str = "R001",
    message: str = "msg",
    details: dict[str, Any] | None = None,
    fix_hint: str | None = None,
) -> MagicMock:
    check = MagicMock()
    check.passed = passed
    check.rule_id = rule_id
    check.message = message
    check.details = details or {}
    check.fix_hint = fix_hint
    return check


class TestCleanProject:
    def test_clean_project(
        self, hook: QualityCheckHook, context: dict[str, str], mocker: Any
    ) -> None:
        """Mock audit_project -> 0 violations => has_violations=False."""
        audit_result = _make_audit_result(
            [
                _make_check(passed=True, rule_id="L001", message="ok"),
            ]
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.audit_project",
            return_value=audit_result,
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.format_agent",
            return_value={
                "failed": [],
                "passed": ["L001: ok"],
                "score": 10,
                "grade": "A",
            },
        )

        result = hook.execute(context)

        assert result.metadata["has_violations"] is False
        assert result.metadata["violations"] == []
        assert "clean" in result.metadata["summary"].lower()


class TestViolationsFound:
    def test_violations_found(
        self,
        hook: QualityCheckHook,
        context: dict[str, str],
        mocker: Any,
    ) -> None:
        """Mock audit_project -> 3 failed checks without inner lists.

        Expects 3 fallback violations.
        """
        failed_items = [
            {
                "rule_id": "L001",
                "message": "err1",
                "details": {"file": "a.py", "line": 1},
                "fix_hint": None,
            },
            {
                "rule_id": "L002",
                "message": "err2",
                "details": {"file": "b.py", "line": 2},
                "fix_hint": None,
            },
            {
                "rule_id": "T001",
                "message": "err3",
                "details": {"file": "c.py", "line": 3},
                "fix_hint": None,
            },
        ]
        audit_result = _make_audit_result(
            [
                _make_check(passed=False, rule_id="L001"),
                _make_check(passed=False, rule_id="L002"),
                _make_check(passed=False, rule_id="T001"),
            ]
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.audit_project",
            return_value=audit_result,
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.format_agent",
            return_value={
                "failed": failed_items,
                "passed": [],
                "score": 0,
                "grade": "F",
            },
        )

        result = hook.execute(context)

        assert result.metadata["has_violations"] is True
        assert len(result.metadata["violations"]) == 3
        for v in result.metadata["violations"]:
            assert "file" in v
            assert "line" in v
            assert "message" in v
            assert "code" in v
            assert "rule_id" in v

    def test_type_violations_expanded(
        self,
        hook: QualityCheckHook,
        context: dict[str, str],
        mocker: Any,
    ) -> None:
        """QUALITY_TYPE with 3 errors in details => 3 individual violations."""
        failed_items = [
            {
                "rule_id": "QUALITY_TYPE",
                "message": "mypy found 3 errors",
                "details": {
                    "error_count": 3,
                    "score": 0.7,
                    "checked": "mypy",
                    "errors": [
                        {
                            "file": "src/foo.py",
                            "line": 10,
                            "message": "Incompatible type",
                            "code": "assignment",
                        },
                        {
                            "file": "src/bar.py",
                            "line": 22,
                            "message": "Missing return",
                            "code": "return",
                        },
                        {
                            "file": "src/baz.py",
                            "line": 5,
                            "message": "Invalid arg",
                            "code": "arg-type",
                        },
                    ],
                },
                "fix_hint": "Fix type errors",
            },
        ]
        audit_result = _make_audit_result(
            [_make_check(passed=False, rule_id="QUALITY_TYPE")]
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.audit_project",
            return_value=audit_result,
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.format_agent",
            return_value={
                "failed": failed_items,
                "passed": [],
                "score": 0.7,
                "grade": "C",
            },
        )

        result = hook.execute(context)

        violations = result.metadata["violations"]
        assert len(violations) == 3
        assert violations[0]["file"] == "src/foo.py"
        assert violations[0]["line"] == 10
        assert violations[0]["message"] == "Incompatible type"
        assert violations[0]["rule_id"] == "QUALITY_TYPE"
        assert violations[1]["file"] == "src/bar.py"
        assert violations[1]["line"] == 22
        assert violations[2]["file"] == "src/baz.py"
        assert violations[2]["line"] == 5

    def test_lint_violations_expanded(
        self,
        hook: QualityCheckHook,
        context: dict[str, str],
        mocker: Any,
    ) -> None:
        """QUALITY_LINT with 2 issues in details => 2 individual violations."""
        failed_items = [
            {
                "rule_id": "QUALITY_LINT",
                "message": "ruff found 2 issues",
                "details": {
                    "issue_count": 2,
                    "score": 0.8,
                    "checked": "ruff",
                    "issues": [
                        {
                            "file": "src/a.py",
                            "line": 3,
                            "code": "E501",
                            "message": "Line too long",
                        },
                        {
                            "file": "src/b.py",
                            "line": 15,
                            "code": "F401",
                            "message": "Unused import",
                        },
                    ],
                },
                "fix_hint": "Run ruff --fix",
            },
        ]
        audit_result = _make_audit_result(
            [_make_check(passed=False, rule_id="QUALITY_LINT")]
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.audit_project",
            return_value=audit_result,
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.format_agent",
            return_value={
                "failed": failed_items,
                "passed": [],
                "score": 0.8,
                "grade": "B",
            },
        )

        result = hook.execute(context)

        violations = result.metadata["violations"]
        assert len(violations) == 2
        assert violations[0]["file"] == "src/a.py"
        assert violations[0]["line"] == 3
        assert violations[0]["code"] == "E501"
        assert violations[0]["message"] == "Line too long"
        assert violations[0]["rule_id"] == "QUALITY_LINT"
        assert violations[1]["file"] == "src/b.py"
        assert violations[1]["code"] == "F401"

    def test_fallback_no_inner_list(
        self,
        hook: QualityCheckHook,
        context: dict[str, str],
        mocker: Any,
    ) -> None:
        """QUALITY_FORMAT with no errors/issues list => single fallback violation."""
        failed_items = [
            {
                "rule_id": "QUALITY_FORMAT",
                "message": "3 files unformatted",
                "details": {"unformatted_count": 3},
                "fix_hint": "Run ruff format",
            },
        ]
        audit_result = _make_audit_result(
            [_make_check(passed=False, rule_id="QUALITY_FORMAT")]
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.audit_project",
            return_value=audit_result,
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.format_agent",
            return_value={
                "failed": failed_items,
                "passed": [],
                "score": 0.5,
                "grade": "D",
            },
        )

        result = hook.execute(context)

        violations = result.metadata["violations"]
        assert len(violations) == 1
        assert violations[0]["message"] == "3 files unformatted"
        assert violations[0]["file"] == ""
        assert violations[0]["line"] == 0
        assert violations[0]["rule_id"] == "QUALITY_FORMAT"

    def test_mixed_categories(
        self,
        hook: QualityCheckHook,
        context: dict[str, str],
        mocker: Any,
    ) -> None:
        """1 QUALITY_TYPE (2 errors) + 1 QUALITY_LINT (3 issues) => 5 violations."""
        failed_items = [
            {
                "rule_id": "QUALITY_TYPE",
                "message": "mypy found 2 errors",
                "details": {
                    "error_count": 2,
                    "score": 0.8,
                    "errors": [
                        {"file": "x.py", "line": 1, "message": "err1", "code": "misc"},
                        {"file": "y.py", "line": 2, "message": "err2", "code": "misc"},
                    ],
                },
                "fix_hint": None,
            },
            {
                "rule_id": "QUALITY_LINT",
                "message": "ruff found 3 issues",
                "details": {
                    "issue_count": 3,
                    "score": 0.6,
                    "issues": [
                        {"file": "a.py", "line": 10, "code": "E501", "message": "long"},
                        {
                            "file": "b.py",
                            "line": 20,
                            "code": "F401",
                            "message": "unused",
                        },
                        {
                            "file": "c.py",
                            "line": 30,
                            "code": "I001",
                            "message": "unsorted",
                        },
                    ],
                },
                "fix_hint": None,
            },
        ]
        audit_result = _make_audit_result(
            [
                _make_check(passed=False, rule_id="QUALITY_TYPE"),
                _make_check(passed=False, rule_id="QUALITY_LINT"),
            ]
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.audit_project",
            return_value=audit_result,
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.format_agent",
            return_value={
                "failed": failed_items,
                "passed": [],
                "score": 0.5,
                "grade": "D",
            },
        )

        result = hook.execute(context)

        violations = result.metadata["violations"]
        assert len(violations) == 5
        assert result.metadata["summary"] == "5 violation(s)"

    def test_empty_errors_list(
        self,
        hook: QualityCheckHook,
        context: dict[str, str],
        mocker: Any,
    ) -> None:
        """Empty errors list => no violations for that check."""
        failed_items = [
            {
                "rule_id": "QUALITY_TYPE",
                "message": "mypy found 0 errors",
                "details": {"error_count": 0, "errors": []},
                "fix_hint": None,
            },
        ]
        audit_result = _make_audit_result(
            [_make_check(passed=False, rule_id="QUALITY_TYPE")]
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.audit_project",
            return_value=audit_result,
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.format_agent",
            return_value={
                "failed": failed_items,
                "passed": [],
                "score": 0.9,
                "grade": "A",
            },
        )

        result = hook.execute(context)

        assert result.metadata["violations"] == []
        assert result.metadata["has_violations"] is False

    def test_none_details(
        self,
        hook: QualityCheckHook,
        context: dict[str, str],
        mocker: Any,
    ) -> None:
        """None details on failed item => single fallback violation."""
        failed_items = [
            {
                "rule_id": "QUALITY_TYPE",
                "message": "check failed",
                "details": None,
                "fix_hint": None,
            },
        ]
        audit_result = _make_audit_result(
            [_make_check(passed=False, rule_id="QUALITY_TYPE")]
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.audit_project",
            return_value=audit_result,
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.format_agent",
            return_value={
                "failed": failed_items,
                "passed": [],
                "score": 0,
                "grade": "F",
            },
        )

        result = hook.execute(context)

        violations = result.metadata["violations"]
        assert len(violations) == 1
        assert violations[0]["message"] == "check failed"
        assert violations[0]["file"] == ""
        assert violations[0]["line"] == 0

    def test_mixed_pass_fail(
        self,
        hook: QualityCheckHook,
        context: dict[str, str],
        mocker: Any,
    ) -> None:
        """1 passed + 1 failed check => only failed check's violations."""
        failed_items = [
            {
                "rule_id": "QUALITY_LINT",
                "message": "1 issue",
                "details": {
                    "issue_count": 1,
                    "issues": [
                        {
                            "file": "z.py",
                            "line": 5,
                            "code": "E501",
                            "message": "long line",
                        },
                    ],
                },
                "fix_hint": None,
            },
        ]
        audit_result = _make_audit_result(
            [
                _make_check(passed=True, rule_id="QUALITY_TYPE"),
                _make_check(passed=False, rule_id="QUALITY_LINT"),
            ]
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.audit_project",
            return_value=audit_result,
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.format_agent",
            return_value={
                "failed": failed_items,
                "passed": ["QUALITY_TYPE: ok"],
                "score": 0.9,
                "grade": "A",
            },
        )

        result = hook.execute(context)

        violations = result.metadata["violations"]
        assert len(violations) == 1
        assert violations[0]["file"] == "z.py"
        assert violations[0]["rule_id"] == "QUALITY_LINT"


class TestDefaultCategories:
    def test_default_categories(
        self,
        hook: QualityCheckHook,
        context: dict[str, str],
        mocker: Any,
    ) -> None:
        """No categories param => calls audit_project twice (lint + type)."""
        audit_result = _make_audit_result()
        mock_audit = mocker.patch(
            "axm_audit.hooks.quality_check.audit_project",
            return_value=audit_result,
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.format_agent",
            return_value={"failed": [], "passed": [], "score": 10, "grade": "A"},
        )

        hook.execute(context)

        assert mock_audit.call_count == 2
        cats_called = [
            call.kwargs.get("category") or call.args[1]
            for call in mock_audit.call_args_list
        ]
        assert "lint" in cats_called
        assert "type" in cats_called


class TestCustomCategories:
    def test_custom_categories(
        self,
        hook: QualityCheckHook,
        context: dict[str, str],
        mocker: Any,
    ) -> None:
        """categories=["lint"] => calls audit_project once."""
        audit_result = _make_audit_result()
        mock_audit = mocker.patch(
            "axm_audit.hooks.quality_check.audit_project",
            return_value=audit_result,
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.format_agent",
            return_value={"failed": [], "passed": [], "score": 10, "grade": "A"},
        )

        hook.execute(context, categories=["lint"])

        assert mock_audit.call_count == 1


class TestInvalidWorkingDir:
    def test_invalid_working_dir(self, hook: QualityCheckHook) -> None:
        """Non-existent dir => has_violations=False, no crash."""
        context = {"working_dir": "/nonexistent/path/that/does/not/exist"}

        result = hook.execute(context)

        assert result.metadata["has_violations"] is False


class TestAuditCrash:
    def test_audit_crash(
        self, hook: QualityCheckHook, context: dict[str, str], mocker: Any
    ) -> None:
        """Mock audit_project raises => logs warning, has_violations=False."""
        mocker.patch(
            "axm_audit.hooks.quality_check.audit_project",
            side_effect=RuntimeError("boom"),
        )

        result = hook.execute(context)

        assert result.metadata["has_violations"] is False
