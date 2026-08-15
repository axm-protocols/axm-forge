"""Unit tests for AuditTestTool MCP tool."""

from __future__ import annotations

import pytest

from axm_audit.core.test_runner import TestReport
from axm_audit.tools.audit_test import AuditTestTool


class TestAuditTestTool:
    def setup_method(self) -> None:
        self.tool = AuditTestTool()

    def test_name(self) -> None:
        assert self.tool.name == "audit_test"


class TestAuditTestToolInvalidPath:
    def setup_method(self) -> None:
        self.tool = AuditTestTool()

    def test_internal_exception_returns_error_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nominal failure path: a crash inside run_tests becomes
        ``ToolResult(success=False, error=...)`` with a readable message,
        never an unhandled raise.

        Pure unit: ``Path.is_dir`` is stubbed True so the tool reaches the
        (patched, raising) ``run_tests`` without touching the filesystem.
        """

        def _boom(*_a: object, **_kw: object) -> object:
            raise RuntimeError("runner exploded")

        monkeypatch.setattr(
            "axm_audit.core.test_runner.run_tests", _boom, raising=False
        )
        monkeypatch.setattr(
            "axm_audit.tools.audit_test.Path.is_dir", lambda _self: True
        )

        result = AuditTestTool().execute(path="/virtual/project")

        assert result.success is False
        assert result.error is not None
        assert "runner exploded" in result.error

    def test_invalid_path(self) -> None:
        result = self.tool.execute(path="/nonexistent/path/xyz")
        assert result.success is False
        assert "Not a directory" in (result.error or "")


def _report(
    *,
    pytest_return_code: int = 0,
    collected: int = 2,
    target_statuses: list[dict[str, str]] | None = None,
    verdict: bool = True,
) -> TestReport:
    return TestReport(
        passed=collected,
        failed=0,
        errors=0,
        pytest_return_code=pytest_return_code,
        collected=collected,
        target_statuses=target_statuses or [],
        verdict=verdict,
    )


def _execute_stubbed(
    monkeypatch: pytest.MonkeyPatch,
    report: TestReport,
):
    monkeypatch.setattr(
        "axm_audit.core.test_runner.run_tests",
        lambda *_args, **_kwargs: report,
    )
    monkeypatch.setattr(
        "axm_audit.tools.audit_test.Path.is_dir",
        lambda _self: True,
    )
    return AuditTestTool().execute(path="/virtual/project")


def test_complete_verdict_drives_tool_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: a complete successful report drives tool success and green text."""
    report = _report(
        collected=3,
        target_statuses=[{"target": "tests/test_many.py", "status": "validated"}],
    )

    result = _execute_stubbed(monkeypatch, report)

    assert result.success is True
    assert result.data is not None
    assert result.data["verdict"] is True
    assert result.data["collected"] == 3
    assert result.text is not None and "✅" in result.text


def test_zero_collection_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: zero parsed collection fails and remains explicit in tool data."""
    result = _execute_stubbed(
        monkeypatch,
        _report(collected=0, verdict=False),
    )

    assert result.success is False
    assert result.data is not None
    assert result.data["collected"] == 0
    assert result.data["verdict"] is False


def test_missing_and_mistyped_targets_fail_independently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: each missing or mistyped target is identified despite collection."""
    statuses = [
        {"target": "tests/test_missing.py", "status": "missing"},
        {"target": "tests/test_typo.py", "status": "missing"},
    ]
    result = _execute_stubbed(
        monkeypatch,
        _report(collected=7, target_statuses=statuses, verdict=False),
    )

    assert result.success is False
    assert result.data is not None
    assert result.data["target_statuses"] == statuses
    assert "tests/test_missing.py" in (result.text or "")
    assert "tests/test_typo.py" in (result.text or "")


def test_silently_omitted_target_fails_independently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: an existing but uncollected requested target fails the verdict."""
    statuses = [
        {"target": "tests/test_ok.py", "status": "validated"},
        {"target": "tests/test_empty.py", "status": "omitted"},
    ]
    result = _execute_stubbed(
        monkeypatch,
        _report(collected=4, target_statuses=statuses, verdict=False),
    )

    assert result.success is False
    assert result.data is not None
    assert result.data["target_statuses"][1] == statuses[1]
    assert "tests/test_empty.py" in (result.text or "")


def test_non_success_exit_overrides_empty_failure_lists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC5: pytest's non-success code fails even with no parsed failures."""
    result = _execute_stubbed(
        monkeypatch,
        _report(pytest_return_code=3, collected=1, verdict=False),
    )

    assert result.success is False
    assert result.data is not None
    assert result.data["pytest_return_code"] == 3
    assert result.data["verdict"] is False
