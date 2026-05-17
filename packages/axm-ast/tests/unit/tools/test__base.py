"""Unit tests for the shared ``safe_execute`` decorator.

Mirrors src/axm_ast/tools/_base.py.
"""

from __future__ import annotations

import logging

import pytest
from axm.tools.base import ToolResult

from axm_ast.tools._base import safe_execute


class _DummyRaisingTool:
    """Dummy tool whose decorated method raises ``RuntimeError``."""

    @safe_execute
    def execute(self) -> ToolResult:
        raise RuntimeError("boom")


class _DummyPassthroughTool:
    """Dummy tool whose decorated method returns a successful ToolResult."""

    @safe_execute
    def execute(self) -> ToolResult:
        return ToolResult(success=True, data={"k": 1})


def test_safe_execute_returns_failure_toolresult_on_exception() -> None:
    result = _DummyRaisingTool().execute()

    assert isinstance(result, ToolResult)
    assert result.success is False
    assert result.error == "boom"


def test_safe_execute_logs_with_exc_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        _DummyRaisingTool().execute()

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings, "expected at least one WARNING record"
    assert any(r.exc_info is not None for r in warnings), (
        "expected exc_info to be populated on the warning record"
    )


def test_safe_execute_passes_through_success() -> None:
    result = _DummyPassthroughTool().execute()

    assert isinstance(result, ToolResult)
    assert result.success is True
    assert result.data == {"k": 1}
    assert result.error is None
