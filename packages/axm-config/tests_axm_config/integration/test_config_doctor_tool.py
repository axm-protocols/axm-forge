from __future__ import annotations

from pathlib import Path

import pytest

from axm_config.tools import ConfigDoctorTool

pytestmark = pytest.mark.integration


def test_config_doctor_tool_never_mutates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """AC3: execute() twice produces identical output and creates no file."""
    monkeypatch.setenv("AXM_DEMO_KEY", "from-env")
    before = set(tmp_path.rglob("*"))

    first = ConfigDoctorTool().execute(namespace="demo")
    second = ConfigDoctorTool().execute(namespace="demo")

    after = set(tmp_path.rglob("*"))
    assert before == after
    assert first.data == second.data
