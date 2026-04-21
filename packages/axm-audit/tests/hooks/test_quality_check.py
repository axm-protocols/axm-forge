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
    result = MagicMock()
    result.checks = checks or []
    return result


def _make_check(
    *,
    passed: bool,
    rule_id: str = "R001",
    message: str = "msg",
    text: str | None = None,
    fix_hint: str | None = None,
) -> MagicMock:
    check = MagicMock()
    check.passed = passed
    check.rule_id = rule_id
    check.message = message
    check.text = text
    check.fix_hint = fix_hint
    return check


class TestCleanProject:
    def test_clean_project(
        self, hook: QualityCheckHook, context: dict[str, str], mocker: Any
    ) -> None:
        audit_result = _make_audit_result(
            [_make_check(passed=True, rule_id="L001", message="ok")]
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.audit_project",
            return_value=audit_result,
        )

        result = hook.execute(context, categories=["lint"])

        assert result.metadata["has_violations"] is False
        assert "clean" in result.metadata["summary"].lower()


class TestFailedChecks:
    def test_text_block_includes_each_rule_and_its_formatted_text(
        self,
        hook: QualityCheckHook,
        context: dict[str, str],
        mocker: Any,
    ) -> None:
        audit_result = _make_audit_result(
            [
                _make_check(
                    passed=False,
                    rule_id="QUALITY_LINT",
                    message="Lint score: 98/100 (1 issues)",
                    text="• I001 tests/foo.py:1 Import block un-sorted",
                    fix_hint="Run: ruff check --fix src/ tests/",
                ),
                _make_check(
                    passed=False,
                    rule_id="QUALITY_TYPE",
                    message="Type score: 85/100 (3 errors)",
                    text=(
                        "• [type-arg] tests/foo.py:34: Missing type arguments\n"
                        "• [no-any-return] tests/foo.py:36: Returning Any\n"
                        "• [no-untyped-def] tests/foo.py:39: Missing annotation"
                    ),
                    fix_hint="Add type hints to functions and fix type errors",
                ),
            ]
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.audit_project",
            return_value=audit_result,
        )

        result = hook.execute(context, categories=["lint"])

        assert result.metadata["has_violations"] is True
        assert result.metadata["summary"] == "2 failing check(s)"
        assert result.text is not None
        body = result.text
        assert "QUALITY_LINT" in body
        assert "Lint score: 98/100" in body
        assert "I001 tests/foo.py:1" in body
        assert "QUALITY_TYPE" in body
        assert "[type-arg] tests/foo.py:34" in body
        assert "[no-untyped-def] tests/foo.py:39" in body
        assert "fix: Run: ruff check --fix src/ tests/" in body
        assert "fix: Add type hints" in body

    def test_failed_check_without_text_uses_message_fallback(
        self,
        hook: QualityCheckHook,
        context: dict[str, str],
        mocker: Any,
    ) -> None:
        audit_result = _make_audit_result(
            [
                _make_check(
                    passed=False,
                    rule_id="QUALITY_FORMAT",
                    message="3 files unformatted",
                    text=None,
                    fix_hint="Run ruff format",
                )
            ]
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.audit_project",
            return_value=audit_result,
        )

        result = hook.execute(context, categories=["lint"])

        assert result.metadata["has_violations"] is True
        assert result.text is not None
        assert "QUALITY_FORMAT" in result.text
        assert "3 files unformatted" in result.text
        assert "(no detail)" in result.text
        assert "fix: Run ruff format" in result.text

    def test_only_failed_checks_appear_in_text(
        self,
        hook: QualityCheckHook,
        context: dict[str, str],
        mocker: Any,
    ) -> None:
        audit_result = _make_audit_result(
            [
                _make_check(
                    passed=True, rule_id="QUALITY_TYPE", message="ok", text="clean"
                ),
                _make_check(
                    passed=False,
                    rule_id="QUALITY_LINT",
                    message="1 issue",
                    text="• E501 z.py:5 long line",
                ),
            ]
        )
        mocker.patch(
            "axm_audit.hooks.quality_check.audit_project",
            return_value=audit_result,
        )

        result = hook.execute(context, categories=["lint"])

        assert result.metadata["summary"] == "1 failing check(s)"
        assert result.text is not None
        assert "QUALITY_LINT" in result.text
        assert "QUALITY_TYPE" not in result.text


class TestDefaultCategories:
    def test_default_categories(
        self,
        hook: QualityCheckHook,
        context: dict[str, str],
        mocker: Any,
    ) -> None:
        audit_result = _make_audit_result()
        mock_audit = mocker.patch(
            "axm_audit.hooks.quality_check.audit_project",
            return_value=audit_result,
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
        audit_result = _make_audit_result()
        mock_audit = mocker.patch(
            "axm_audit.hooks.quality_check.audit_project",
            return_value=audit_result,
        )

        hook.execute(context, categories=["lint"])

        assert mock_audit.call_count == 1


class TestInvalidWorkingDir:
    def test_invalid_working_dir(self, hook: QualityCheckHook) -> None:
        context = {"working_dir": "/nonexistent/path/that/does/not/exist"}

        result = hook.execute(context)

        assert result.metadata["has_violations"] is False


class TestAuditCrash:
    def test_audit_crash(
        self, hook: QualityCheckHook, context: dict[str, str], mocker: Any
    ) -> None:
        mocker.patch(
            "axm_audit.hooks.quality_check.audit_project",
            side_effect=RuntimeError("boom"),
        )

        result = hook.execute(context)

        assert result.metadata["has_violations"] is False
