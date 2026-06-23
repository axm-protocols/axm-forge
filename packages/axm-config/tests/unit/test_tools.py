from __future__ import annotations

import pytest

from axm_config.tools import ConfigDoctorTool


def test_config_doctor_tool_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC2, AC4: execute() returns ToolResult(success=True) + provenance map."""
    monkeypatch.setenv("AXM_DEMO_KEY", "from-env")

    result = ConfigDoctorTool().execute(namespace="demo")

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["demo.key"]["layer"] == "env"
