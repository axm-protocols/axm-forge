from __future__ import annotations

import dataclasses
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


class TestDeprecatedMode:
    @pytest.mark.usefixtures("_mock_run_tests")
    def test_accepts_deprecated_mode(self, tool, tmp_path):
        """execute(mode='compact') succeeds and returns same data as default."""
        default_result = tool.execute(path=str(tmp_path))
        mode_result = tool.execute(path=str(tmp_path), mode="compact")

        assert default_result.success is True
        assert mode_result.success is True
        assert default_result.data == mode_result.data

    @pytest.mark.usefixtures("_mock_run_tests")
    def test_no_mode_validation(self, tool, tmp_path):
        """execute(mode='bogus') succeeds — no validation, mode is ignored."""
        result = tool.execute(path=str(tmp_path), mode="bogus")

        assert result.success is True
