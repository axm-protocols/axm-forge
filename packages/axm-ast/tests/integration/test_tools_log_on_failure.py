"""Integration: tool failures emit WARNING with exc_info and structured result."""

from __future__ import annotations

import logging

import pytest

from axm_ast.tools.impact import ImpactTool

pytestmark = pytest.mark.integration


def test_impact_tool_logs_when_target_path_invalid(
    caplog: pytest.LogCaptureFixture,
) -> None:
    tool = ImpactTool()

    with caplog.at_level(logging.WARNING, logger="axm_ast.tools.impact"):
        result = tool.execute(path="/does/not/exist", symbol="foo")

    assert result.success is False

    records = [
        r
        for r in caplog.records
        if r.name == "axm_ast.tools.impact" and r.levelno == logging.WARNING
    ]
    assert records, "expected a WARNING record from axm_ast.tools.impact"
    assert any(r.exc_info is not None for r in records), (
        "expected exc_info to be populated on the warning record"
    )
