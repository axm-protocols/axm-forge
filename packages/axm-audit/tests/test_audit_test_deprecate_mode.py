from __future__ import annotations

import dataclasses
import subprocess
import sys
from unittest.mock import MagicMock

import pytest


@dataclasses.dataclass
class _FakeReport:
    passed: int = 5
    failed: int = 0
    errors: int = 0
    summary: str = "all green"


@pytest.fixture()
def tool():
    from axm_audit.tools.audit_test import AuditTestTool

    return AuditTestTool()


@pytest.fixture()
def _mock_run_tests(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock = MagicMock(return_value=_FakeReport())
    monkeypatch.setattr("axm_audit.core.test_runner.run_tests", mock)
    return mock


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_mock_run_tests")
def test_accepts_deprecated_mode(tool, tmp_path):
    """execute(mode='compact') succeeds and returns same data as default."""
    default_result = tool.execute(path=str(tmp_path))
    mode_result = tool.execute(path=str(tmp_path), mode="compact")

    assert default_result.success is True
    assert mode_result.success is True
    assert default_result.data == mode_result.data


@pytest.mark.usefixtures("_mock_run_tests")
def test_no_mode_validation(tool, tmp_path):
    """execute(mode='bogus') succeeds — no validation, mode is ignored."""
    result = tool.execute(path=str(tmp_path), mode="bogus")

    assert result.success is True


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


def test_cli_no_mode_flag():
    """CLI 'test --help' must not expose a --mode flag."""
    proc = subprocess.run(
        [sys.executable, "-m", "axm_audit", "test", "--help"],
        capture_output=True,
        text=True,
    )
    assert "--mode" not in proc.stdout, "--mode flag should be removed from CLI"
