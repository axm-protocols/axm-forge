from __future__ import annotations

import pytest

from axm_config.doctor import render_doctor_report
from axm_config.tools import ConfigDoctorTool


def test_config_doctor_tool_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC2, AC4: execute() returns ToolResult(success=True) + provenance map."""
    monkeypatch.setenv("AXM_DEMO_KEY", "from-env")

    result = ConfigDoctorTool().execute(namespace="demo")

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["demo.key"]["layer"] == "env"


def test_execute_text_one_line_per_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC1: text is a non-None str with one ``<key>: <layer>`` line per key."""
    monkeypatch.setenv("AXM_DEMO_KEY", "from-env")

    result = ConfigDoctorTool().execute(namespace="demo")

    assert isinstance(result.text, str)
    assert "demo.key: env" in result.text.splitlines()


def test_execute_data_payload_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: data stays the raw provenance report dict, text is additive."""
    monkeypatch.setenv("AXM_DEMO_KEY", "from-env")

    result = ConfigDoctorTool().execute(namespace="demo")

    assert result.data == {"demo.key": {"layer": "env", "present": True}}


def test_execute_text_matches_shared_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: text equals the shared render helper applied to the same report."""
    monkeypatch.setenv("AXM_DEMO_KEY", "from-env")

    result = ConfigDoctorTool().execute(namespace="demo")

    assert result.text == render_doctor_report(result.data)
