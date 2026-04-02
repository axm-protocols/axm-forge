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
        """Mock audit_project -> 3 violations => has_violations=True."""
        violations = [
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
            return_value={"failed": violations, "passed": [], "score": 0, "grade": "F"},
        )

        result = hook.execute(context)

        assert result.metadata["has_violations"] is True
        assert len(result.metadata["violations"]) == 3
        for v in result.metadata["violations"]:
            assert "file" in v
            assert "line" in v
            assert "message" in v
            assert "code" in v or "rule_id" in v


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
