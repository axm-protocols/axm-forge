from __future__ import annotations

from pathlib import Path

import pytest

from axm_config import ProfileIsolationTool
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


def test_profile_isolation_tool_serves_ci_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AC1: the isolation tool serves the dashed profile ``ci-2``."""
    monkeypatch.setenv("AXM_HOME", str(tmp_path))

    result = ProfileIsolationTool().execute(profile="ci-2")

    assert result.success is True
    assert result.data["profile"] == "ci-2"


def test_profile_isolation_tool_serves_dev_audit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AC1: the isolation tool serves the dashed profile ``dev-audit``."""
    monkeypatch.setenv("AXM_HOME", str(tmp_path))

    result = ProfileIsolationTool().execute(profile="dev-audit")

    assert result.success is True
    assert result.data["profile"] == "dev-audit"


def test_profile_isolation_tool_refuses_leading_digit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AC2: the tool refuses ``1dev`` and names the invalid profile."""
    monkeypatch.setenv("AXM_HOME", str(tmp_path))

    result = ProfileIsolationTool().execute(profile="1dev")

    assert result.success is False
    assert "1dev" in result.error
