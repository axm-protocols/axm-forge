from __future__ import annotations

import dataclasses
from importlib.metadata import entry_points
from unittest.mock import MagicMock

import pytest


@dataclasses.dataclass
class _FakeReport:
    passed: int = 5
    failed: int = 0
    errors: int = 0
    summary: str = "all green"
    skipped: int = 0
    duration: float = 0.1
    coverage: float | None = None
    coverage_by_file: dict[str, float] | None = None
    failures: list[object] | None = None
    timed_out: bool = False
    pytest_return_code: int = 0
    collected: int = 5
    target_statuses: list[dict[str, str]] = dataclasses.field(default_factory=list)
    verdict: bool = True


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


@pytest.mark.integration
def test_registration_has_no_verdict_bypass(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """AC6: the sole installed audit_test surface cannot bypass its verdict."""
    from axm_audit.tools.audit_test import AuditTestTool

    registrations = [
        entry for entry in entry_points(group="axm.tools") if entry.name == "audit_test"
    ]
    assert len(registrations) == 1
    assert registrations[0].load() is AuditTestTool

    report = _FakeReport(passed=0, collected=0, verdict=False)
    monkeypatch.setattr(
        "axm_audit.core.test_runner.run_tests",
        MagicMock(return_value=report),
    )

    result = AuditTestTool().execute(path=str(tmp_path), mode="compact")

    assert result.success is False
    assert result.data is not None
    assert result.data["verdict"] is False
    assert "❌" in (result.text or "")
